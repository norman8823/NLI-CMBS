"""Service to ingest CMBS news articles from RSS feeds and generate AI summaries."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import httpx

from nli_cmbs.ai.client import AnthropicClient
from nli_cmbs.db.models import MarketArticle

logger = logging.getLogger(__name__)

TREPP_RSS_URL = "https://www.trepp.com/trepptalk/topic/cmbs-news/rss.xml"


async def fetch_rss_feed(url: str = TREPP_RSS_URL) -> list[dict]:
    """Fetch and parse RSS feed, return list of article dicts.

    Returns list sorted by published_date descending.
    """
    import feedparser

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url)
        response.raise_for_status()

    feed = feedparser.parse(response.text)
    articles: list[dict] = []

    for entry in feed.entries:
        # Parse published date
        pub_date = None
        if hasattr(entry, "published"):
            try:
                pub_date = parsedate_to_datetime(entry.published)
            except Exception:
                pass
        if not pub_date and hasattr(entry, "published_parsed") and entry.published_parsed:
            from time import mktime
            pub_date = datetime.fromtimestamp(mktime(entry.published_parsed), tz=timezone.utc)
        if not pub_date:
            pub_date = datetime.now(timezone.utc)

        # Extract author name from "email (Name)" format
        author = None
        if hasattr(entry, "author"):
            author_raw = entry.author
            match = re.search(r"\((.+?)\)", author_raw)
            author = match.group(1) if match else author_raw

        articles.append({
            "url": entry.link,
            "title": entry.title,
            "author": author,
            "published_date": pub_date,
            "excerpt": entry.get("summary", entry.get("description", "")),
        })

    articles.sort(key=lambda a: a["published_date"], reverse=True)
    return articles


async def fetch_article_body(url: str) -> str | None:
    """Fetch full article text from a Trepp/HubSpot article page.

    Returns cleaned plain text, or None if fetch fails.
    """
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
    except httpx.HTTPError:
        logger.warning("Failed to fetch article body: %s", url)
        return None

    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(response.text, "html.parser")

        # HubSpot blog posts: try common selectors
        body = (
            soup.find("div", class_=re.compile(r"post-body|hs_cos_wrapper_post_body|blog-post__body"))
            or soup.find("div", {"id": re.compile(r"hs_cos_wrapper_post_body")})
            or soup.find("article")
            or soup.find("div", class_=re.compile(r"blog-content|entry-content"))
        )

        if not body:
            logger.warning("Could not find article body element: %s", url)
            return None

        # Remove script/style/nav elements
        for tag in body.find_all(["script", "style", "nav", "header", "footer", "iframe"]):
            tag.decompose()

        text = body.get_text(separator="\n", strip=True)
        # Collapse excessive whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip() if text.strip() else None

    except Exception:
        logger.warning("Failed to parse article body: %s", url, exc_info=True)
        return None


async def generate_article_summary(
    ai_client: AnthropicClient,
    title: str,
    body_text: str,
) -> dict:
    """Use Claude API to generate summary and extract key themes.

    Returns dict with 'summary' and 'key_themes' keys.
    """
    truncated = body_text[:4000] if body_text else ""

    system_prompt = (
        "You are a CMBS market analyst. You summarize news articles concisely and factually. "
        "Do NOT provide investment recommendations or buy/hold/sell guidance."
    )

    user_prompt = f"""Summarize this article in 2-3 sentences, focusing on key facts and market developments.
Then extract 3-5 key themes as short phrases. Do not include investment recommendations.

Title: {title}
Article: {truncated}

Respond in JSON format only:
{{
    "summary": "...",
    "key_themes": ["theme1", "theme2", ...]
}}"""

    try:
        result = await ai_client.generate_report(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.2,
        )
        # Extract JSON from response (may have markdown fences)
        json_match = re.search(r"\{[\s\S]*\}", result.text)
        if json_match:
            return json.loads(json_match.group())
        return {"summary": result.text.strip(), "key_themes": []}
    except Exception:
        logger.warning("Failed to generate AI summary for: %s", title, exc_info=True)
        return {"summary": None, "key_themes": None}


async def ingest_new_articles(
    db,
    since_days: int = 7,
    fetch_full_text: bool = True,
    generate_summaries: bool = True,
    ai_client: AnthropicClient | None = None,
) -> list[MarketArticle]:
    """Main ingestion function.

    1. Fetch RSS feed
    2. Filter to articles published in last `since_days`
    3. For each article not already in DB (check by URL):
       a. Fetch full article body if fetch_full_text=True
       b. Generate AI summary if generate_summaries=True
       c. Insert into market_articles table
    4. Return list of newly inserted articles
    """
    from sqlalchemy import select

    # 1. Fetch RSS
    articles = await fetch_rss_feed()
    logger.info("Fetched %d articles from RSS feed", len(articles))

    # 2. Filter by date (since_days=0 means ingest all)
    if since_days > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)
        recent = [a for a in articles if a["published_date"] >= cutoff]
        logger.info("Filtered to %d articles from last %d days", len(recent), since_days)
    else:
        recent = articles
        logger.info("Ingesting all %d articles (no date filter)", len(recent))

    # 3. Check which URLs already exist
    existing_urls: set[str] = set()
    if recent:
        urls = [a["url"] for a in recent]
        result = await db.execute(
            select(MarketArticle.url).where(MarketArticle.url.in_(urls))
        )
        existing_urls = {row[0] for row in result.all()}

    new_articles: list[MarketArticle] = []

    for article_data in recent:
        if article_data["url"] in existing_urls:
            continue

        body_text = None
        if fetch_full_text:
            body_text = await fetch_article_body(article_data["url"])

        summary = None
        key_themes = None
        if generate_summaries and ai_client and (body_text or article_data.get("excerpt")):
            text_for_summary = body_text or article_data["excerpt"]
            ai_result = await generate_article_summary(
                ai_client, article_data["title"], text_for_summary
            )
            summary = ai_result.get("summary")
            key_themes = ai_result.get("key_themes")

        article = MarketArticle(
            url=article_data["url"],
            title=article_data["title"],
            author=article_data["author"],
            published_date=article_data["published_date"],
            excerpt=article_data.get("excerpt"),
            body_text=body_text,
            source="Trepp",
            summary=summary,
            key_themes=key_themes,
        )
        db.add(article)
        new_articles.append(article)

    if new_articles:
        await db.commit()

    return new_articles


async def generate_news_digest(
    db,
    ai_client: AnthropicClient,
    days: int = 7,
) -> str:
    """Generate a consolidated digest of recent CMBS news.

    Queries articles from last N days, consolidates themes,
    and generates a narrative summary using Claude.
    """
    from sqlalchemy import select

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(MarketArticle)
        .where(MarketArticle.published_date >= cutoff)
        .order_by(MarketArticle.published_date.desc())
    )
    articles = list(result.scalars().all())

    if not articles:
        return "No articles found in the specified time period."

    # Build article summaries for the prompt
    article_blurbs = []
    for a in articles:
        blurb = f"- **{a.title}** ({a.published_date.strftime('%b %d')})"
        if a.summary:
            blurb += f"\n  {a.summary}"
        if a.key_themes:
            blurb += f"\n  Themes: {', '.join(a.key_themes)}"
        article_blurbs.append(blurb)

    articles_text = "\n\n".join(article_blurbs)

    system_prompt = (
        "You are a senior CMBS market analyst writing a weekly market intelligence digest. "
        "Summarize key themes and trends factually. Do NOT provide investment recommendations, "
        "positioning advice, or buy/hold/sell guidance. Focus on what happened and why it matters."
    )

    user_prompt = f"""Based on the following {len(articles)} CMBS news articles from the past {days} days,
write a consolidated market intelligence digest (3-5 paragraphs).

Identify the top themes, highlight notable trends, and flag emerging risks or developments.
Do not include investment recommendations or portfolio positioning suggestions.

Articles:
{articles_text}"""

    result = await ai_client.generate_report(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.3,
    )
    return result.text

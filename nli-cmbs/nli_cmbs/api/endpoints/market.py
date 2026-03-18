from collections import Counter
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nli_cmbs.db.models import MarketArticle
from nli_cmbs.db.session import get_session
from nli_cmbs.schemas.market import MarketArticleOut, ThemeCount, ThemesOut

router = APIRouter()


@router.get("/news", response_model=list[MarketArticleOut])
async def get_recent_news(
    limit: int = Query(10, ge=1, le=100),
    days: int = Query(7, ge=1, le=90),
    source: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
):
    """Return recent market news articles for dashboard display."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    stmt = (
        select(MarketArticle)
        .where(MarketArticle.published_date >= cutoff)
        .order_by(MarketArticle.published_date.desc())
        .limit(limit)
    )
    if source:
        stmt = stmt.where(MarketArticle.source == source)

    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.get("/themes", response_model=ThemesOut)
async def get_current_themes(
    days: int = Query(7, ge=1, le=90),
    session: AsyncSession = Depends(get_session),
):
    """Return consolidated key themes from recent articles, sorted by frequency."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    result = await session.execute(
        select(MarketArticle.key_themes)
        .where(
            MarketArticle.published_date >= cutoff,
            MarketArticle.key_themes.isnot(None),
        )
    )

    counter: Counter[str] = Counter()
    article_count = 0
    for (themes,) in result.all():
        if themes:
            article_count += 1
            for theme in themes:
                counter[theme.lower().strip()] += 1

    sorted_themes = [
        ThemeCount(theme=theme, count=count)
        for theme, count in counter.most_common()
    ]

    return ThemesOut(themes=sorted_themes, article_count=article_count, days=days)

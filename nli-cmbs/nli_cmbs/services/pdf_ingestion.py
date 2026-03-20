"""Service to ingest PDF research reports into the knowledge base."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from nli_cmbs.ai.client import AnthropicClient
from nli_cmbs.db.models import ResearchReport

logger = logging.getLogger(__name__)


def extract_pdf_text(file_path: str) -> tuple[str, int]:
    """Extract all text from a PDF file using pdfplumber.

    Returns (full_text, page_count).
    """
    import pdfplumber

    pages_text: list[str] = []
    with pdfplumber.open(file_path) as pdf:
        page_count = len(pdf.pages)
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages_text.append(text)

    return "\n\n".join(pages_text), page_count


async def generate_report_summary(
    ai_client: AnthropicClient,
    title: str,
    text: str,
) -> dict:
    """Use Claude to summarize a research report and extract key themes.

    Returns dict with 'summary' and 'key_themes' keys.
    """
    truncated = text[:8000] if text else ""

    system_prompt = (
        "You are a CMBS market analyst. You summarize research reports concisely and factually. "
        "Do NOT provide investment recommendations or buy/hold/sell guidance."
    )

    user_prompt = f"""Summarize this research report in 3-5 sentences, focusing on key findings and market implications.
Then extract 3-7 key themes as short phrases. Do not include investment recommendations.

Title: {title}
Report text: {truncated}

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
        json_match = re.search(r"\{[\s\S]*\}", result.text)
        if json_match:
            return json.loads(json_match.group())
        return {"summary": result.text.strip(), "key_themes": []}
    except Exception:
        logger.warning("Failed to generate AI summary for: %s", title, exc_info=True)
        return {"summary": None, "key_themes": None}


async def ingest_pdf_reports(
    db,
    path: str,
    generate_summaries: bool = True,
    ai_client: AnthropicClient | None = None,
    dry_run: bool = False,
) -> list[ResearchReport]:
    """Ingest PDF files from a file or directory.

    Deduplicates by filename. Extracts text, optionally generates AI summaries.
    Returns list of newly inserted ResearchReport records.
    """
    from sqlalchemy import select

    target = Path(path)
    if target.is_file():
        pdf_files = [target] if target.suffix.lower() == ".pdf" else []
    elif target.is_dir():
        pdf_files = sorted(target.glob("*.pdf"))
    else:
        logger.error("Path does not exist: %s", path)
        return []

    if not pdf_files:
        logger.info("No PDF files found at: %s", path)
        return []

    logger.info("Found %d PDF files", len(pdf_files))

    # Check which filenames already exist
    filenames = [f.name for f in pdf_files]
    existing_filenames: set[str] = set()
    if not dry_run:
        result = await db.execute(
            select(ResearchReport.filename).where(ResearchReport.filename.in_(filenames))
        )
        existing_filenames = {row[0] for row in result.all()}

    new_reports: list[ResearchReport] = []

    for pdf_file in pdf_files:
        if pdf_file.name in existing_filenames:
            logger.info("Skipping duplicate: %s", pdf_file.name)
            continue

        if dry_run:
            # Create a placeholder for dry-run display
            report = ResearchReport(
                filename=pdf_file.name,
                title=pdf_file.stem.replace("_", " ").replace("-", " "),
            )
            new_reports.append(report)
            continue

        # Extract text
        try:
            full_text, page_count = extract_pdf_text(str(pdf_file))
        except Exception:
            logger.warning("Failed to extract text from: %s", pdf_file.name, exc_info=True)
            continue

        title = pdf_file.stem.replace("_", " ").replace("-", " ")

        # Generate AI summary
        summary = None
        key_themes = None
        if generate_summaries and ai_client and full_text:
            ai_result = await generate_report_summary(ai_client, title, full_text)
            summary = ai_result.get("summary")
            key_themes = ai_result.get("key_themes")

        report = ResearchReport(
            filename=pdf_file.name,
            title=title,
            page_count=page_count,
            full_text=full_text if full_text else None,
            summary=summary,
            key_themes=key_themes,
        )
        db.add(report)
        new_reports.append(report)

    if new_reports and not dry_run:
        await db.commit()

    return new_reports

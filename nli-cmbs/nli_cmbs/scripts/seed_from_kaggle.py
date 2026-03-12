"""Seed CikMapping table from the Kaggle CMBS deals dataset.

Usage:
    python -m nli_cmbs.scripts.seed_from_kaggle
"""

import asyncio
import re

import pandas as pd
from sqlalchemy import select

from nli_cmbs.db.engine import engine
from nli_cmbs.db.models import CikMapping
from nli_cmbs.db.session import async_session_factory

KAGGLE_DATASET = "cmdrvl/cmbs-deals-edgar-cik-and-collateral-distribution"
CSV_FILENAME = "cmbs_deals_edgar_ciks.csv"

# Known shelf → depositor name mappings for major CMBS issuers
SHELF_DEPOSITORS: dict[str, str] = {
    "BANK": "Morgan Stanley Capital I Inc.",
    "BMARK": "Citi Real Estate Funding Inc.",
    "BBCMS": "Barclays Commercial Mortgage Securities LLC",
    "BMO": "BMO Mortgage Trust",
    "WF": "Wells Fargo Commercial Mortgage Securities Inc.",
    "WFCM": "Wells Fargo Commercial Mortgage Securities Inc.",
    "UBS": "UBS Commercial Mortgage Trust",
    "UBSCM": "UBS Commercial Mortgage Trust",
    "MSCI": "Morgan Stanley Capital I Inc.",
    "GSMS": "GS Mortgage Securities Corporation II",
    "CCMT": "Citigroup Commercial Mortgage Trust",
    "CSAIL": "Column Financial Inc.",
    "CSMC": "Column Financial Inc.",
    "JPM": "J.P. Morgan Chase Commercial Mortgage Securities Corp.",
    "JPMDB": "J.P. Morgan Chase Commercial Mortgage Securities Corp.",
    "CD": "CD Mortgage Trust",
    "CF": "Citigroup Commercial Mortgage Trust",
    "MSBAM": "Morgan Stanley Bank of America Merrill Lynch Trust",
    "COMM": "Deutsche Mortgage & Asset Receiving Corp.",
    "MSWF": "Morgan Stanley Capital I Inc.",
    "DBJPM": "Deutsche Mortgage & Asset Receiving Corp.",
    "DBGS": "Deutsche Mortgage & Asset Receiving Corp.",
    "BACM": "Bank of America Merrill Lynch Commercial Mortgage Inc.",
    "FIVE": "Morgan Stanley Capital I Inc.",
    "3650": "3650R Commercial Mortgage Trust",
}


def _extract_vintage(deal_ticker: str) -> int | None:
    """Extract 4-digit year from a deal ticker like 'BMARK 2023-V3'."""
    match = re.search(r"(\d{4})", deal_ticker)
    return int(match.group(1)) if match else None


async def seed() -> None:
    import kagglehub

    path = kagglehub.dataset_download(KAGGLE_DATASET)
    df = pd.read_csv(f"{path}/{CSV_FILENAME}")

    loaded = 0
    skipped = 0

    async with async_session_factory() as session:
        for _, row in df.iterrows():
            deal_ticker = str(row["DEAL_SHORT_NAME"]).strip()
            existing = await session.execute(
                select(CikMapping).where(CikMapping.deal_ticker == deal_ticker)
            )
            if existing.scalar_one_or_none():
                skipped += 1
                continue

            shelf = str(row["SHELF"]).strip()
            mapping = CikMapping(
                deal_ticker=deal_ticker,
                trust_name=str(row["DEAL_NAME"]).strip(),
                depositor_cik=str(int(row["EDGAR_CIK"])),
                issuer_shelf=shelf,
                depositor_name=SHELF_DEPOSITORS.get(shelf),
                verified=True,
                source="kaggle_cmdrvl",
            )
            session.add(mapping)
            loaded += 1

        await session.commit()

    # Summary
    vintages = df["VINTAGE"].dropna().astype(int)
    shelves = df["SHELF"].nunique()
    print("\nSeed complete:")
    print(f"  Records loaded:  {loaded}")
    print(f"  Records skipped: {skipped} (already existed)")
    print(f"  Shelves covered: {shelves}")
    print(f"  Vintage range:   {vintages.min()}–{vintages.max()}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())

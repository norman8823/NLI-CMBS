"""Known CMBS issuer shelves with depositor CIKs and trust name patterns.

This is the LAST-RESORT fallback for CIK resolution. Most deals should resolve
from the CikMapping table (seeded from Kaggle) or EDGAR full-text search.

IMPORTANT: Some shelves rotate depositors across vintages (e.g., BMARK uses
Deutsche Mortgage, JPMorgan, Goldman Sachs, or Citigroup depending on year/series).
The `depositor_ciks` list contains ALL known depositors for each shelf.
Strategy 3 iterates through each depositor CIK until one matches.

All CIKs verified against data.sec.gov/submissions/ on 2026-03-11.
"""

CMBS_SHELVES: dict[str, dict] = {
    "BMARK": {
        "depositor_name": "Multiple (rotates by vintage)",
        "depositor_ciks": [
            "0001013454",  # DEUTSCHE MORTGAGE & ASSET RECEIVING CORP
            "0001013611",  # JP MORGAN CHASE COMMERCIAL MORTGAGE SECURITIES CORP
            "0001004158",  # GS MORTGAGE SECURITIES CORP II
            "0001258361",  # CITIGROUP COMMERCIAL MORTGAGE SECURITIES INC
        ],
        "trust_name_pattern": "Benchmark {year}-{series} Mortgage Trust",
        "description": "Benchmark conduit program (multi-depositor)",
    },
    "BANK5": {
        "depositor_name": "Morgan Stanley Capital I Inc.",
        "depositor_ciks": ["0001547361"],
        "trust_name_pattern": "BANK5 {year}-{series} Mortgage Trust",
        "description": "Bank of America/Morgan Stanley conduit",
    },
    "BANK": {
        "depositor_name": "Morgan Stanley Capital I Inc.",
        "depositor_ciks": ["0001547361"],
        "trust_name_pattern": "BANK {year}-{series}",
        "description": "Bank of America/Morgan Stanley conduit (legacy)",
    },
    "GSMS": {
        "depositor_name": "GS Mortgage Securities Corporation II",
        "depositor_ciks": ["0001004158"],
        "trust_name_pattern": "GS Mortgage Securities Trust {year}-{series}",
        "description": "Goldman Sachs conduit",
    },
    "WFCM": {
        "depositor_name": "Wells Fargo Commercial Mortgage Securities Inc.",
        "depositor_ciks": ["0000850779"],
        "trust_name_pattern": "Wells Fargo Commercial Mortgage Trust {year}-{series}",
        "description": "Wells Fargo conduit",
    },
    "JPMCC": {
        "depositor_name": "J.P. Morgan Chase Commercial Mortgage Securities Corp.",
        "depositor_ciks": ["0001013611"],
        "trust_name_pattern": "J.P. Morgan Chase Commercial Mortgage Securities Trust {year}-{series}",
        "description": "JPMorgan conduit",
    },
    "COMM": {
        "depositor_name": "Deutsche Mortgage & Asset Receiving Corp.",
        "depositor_ciks": ["0001013454"],
        "trust_name_pattern": "COMM {year}-{series} Mortgage Trust",
        "description": "Deutsche Bank conduit",
    },
    "MSC": {
        "depositor_name": "Morgan Stanley Capital I Inc.",
        "depositor_ciks": ["0001547361"],
        "trust_name_pattern": "Morgan Stanley Capital I Trust {year}-{series}",
        "description": "Morgan Stanley conduit (legacy)",
    },
    "CGCMT": {
        "depositor_name": "Citigroup Commercial Mortgage Securities Inc.",
        "depositor_ciks": ["0001258361"],
        "trust_name_pattern": "Citigroup Commercial Mortgage Trust {year}-{series}",
        "description": "Citigroup conduit",
    },
    "BBCMS": {
        "depositor_name": "Barclays Commercial Mortgage Securities LLC",
        "depositor_ciks": ["0001541480"],
        "trust_name_pattern": "BBCMS Mortgage Trust {year}-{series}",
        "description": "Barclays conduit",
    },
    "BMO": {
        "depositor_name": "BMO Commercial Mortgage Securities LLC",
        "depositor_ciks": ["0001861132"],
        "trust_name_pattern": "BMO {year}-{series} Mortgage Trust",
        "description": "BMO conduit",
    },
    "MSCI": {
        "depositor_name": "Morgan Stanley Capital I Inc.",
        "depositor_ciks": ["0001547361"],
        "trust_name_pattern": "Morgan Stanley Capital I Trust {year}-{series}",
        "description": "Morgan Stanley Capital I conduit",
    },
}

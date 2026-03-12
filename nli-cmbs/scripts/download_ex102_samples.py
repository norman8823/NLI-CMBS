"""Download real EX-102 XML samples directly from EDGAR (no database required).

Usage: python scripts/download_ex102_samples.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lxml import html

from nli_cmbs.edgar.client import EdgarClient
from nli_cmbs.edgar.seed_data import CMBS_SHELVES


async def find_abs_ee_filings(client: EdgarClient, cik: str, limit: int = 5) -> list[dict]:
    """Fetch ABS-EE filings from EDGAR submissions API."""
    submissions = await client.get_submissions(cik)
    recent = submissions.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accessions = recent.get("accessionNumber", [])
    dates = recent.get("filingDate", [])

    results = []
    for i, form in enumerate(forms):
        if form == "ABS-EE":
            results.append({
                "accession_number": accessions[i],
                "filing_date": dates[i],
            })
            if len(results) >= limit:
                break

    results.sort(key=lambda x: x["filing_date"], reverse=True)
    return results


async def find_ex102_url(client: EdgarClient, accession: str, cik: str) -> str | None:
    """Parse filing index HTML to find EX-102 XML URL."""
    cik_num = str(int(cik))
    acc_no_dashes = accession.replace("-", "")
    index_url = (
        f"https://www.sec.gov/Archives/edgar/data/"
        f"{cik_num}/{acc_no_dashes}/{accession}-index.htm"
    )

    response = await client.download_filing_document(index_url)
    tree = html.fromstring(response)

    for row in tree.xpath('//table[@class="tableFile"]//tr'):
        cells = row.xpath("td")
        if len(cells) >= 4:
            doc_type = cells[3].text_content().strip()
            link = cells[2].xpath(".//a/@href")
            if link and "EX-102" in doc_type.upper() and link[0].endswith(".xml"):
                doc_url = link[0]
                if not doc_url.startswith("http"):
                    doc_url = f"https://www.sec.gov{doc_url}"
                return doc_url

    return None


async def download_deal(client: EdgarClient, shelf: str, cik: str, label: str) -> tuple[bytes | None, dict]:
    """Try to download EX-102 for a deal using depositor CIK."""
    info = {"shelf": shelf, "cik": cik, "label": label}
    print(f"\n--- Trying {label} (shelf={shelf}, CIK={cik}) ---")

    try:
        filings = await find_abs_ee_filings(client, cik)
        if not filings:
            print(f"  No ABS-EE filings found for CIK {cik}")
            return None, info

        latest = filings[0]
        print(f"  Latest filing: {latest['accession_number']} ({latest['filing_date']})")
        info["accession"] = latest["accession_number"]
        info["filing_date"] = latest["filing_date"]

        ex102_url = await find_ex102_url(client, latest["accession_number"], cik)
        if not ex102_url:
            print("  No EX-102 XML found in filing index")
            return None, info

        print(f"  EX-102 URL: {ex102_url}")
        info["ex102_url"] = ex102_url

        xml_bytes = await client.download_filing_document(ex102_url)
        print(f"  Downloaded: {len(xml_bytes):,} bytes")
        info["size"] = len(xml_bytes)
        return xml_bytes, info

    except Exception as e:
        print(f"  Error: {e}")
        return None, info


async def main():
    fixtures_dir = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    client = EdgarClient()
    results = []

    try:
        # Deal 1: BMARK - try each depositor CIK
        bmark_ciks = CMBS_SHELVES["BMARK"]["depositor_ciks"]
        xml1 = None
        info1 = {}
        for cik in bmark_ciks:
            xml1, info1 = await download_deal(client, "BMARK", cik, "BMARK 2024-V6")
            if xml1:
                break

        if xml1:
            out1 = fixtures_dir / "ex102_bmark_2024_v6.xml"
            out1.write_bytes(xml1)
            print(f"\n  Saved to {out1} ({len(xml1):,} bytes)")
            results.append(("BMARK", out1, info1))
        else:
            print("\n  FAILED: Could not download BMARK EX-102")

        # Deal 2: BANK5 depositor CIK
        bank5_ciks = CMBS_SHELVES["BANK5"]["depositor_ciks"]
        xml2 = None
        info2 = {}
        for cik in bank5_ciks:
            xml2, info2 = await download_deal(client, "BANK5", cik, "BANK5 2024-5YR9")
            if xml2:
                break

        if not xml2:
            # Fallback: try WFCM
            wfcm_ciks = CMBS_SHELVES["WFCM"]["depositor_ciks"]
            for cik in wfcm_ciks:
                xml2, info2 = await download_deal(client, "WFCM", cik, "WFCM 2024-C64")
                if xml2:
                    break

        if xml2:
            shelf_lower = info2["shelf"].lower()
            out2 = fixtures_dir / f"ex102_{shelf_lower}_second_deal.xml"
            out2.write_bytes(xml2)
            print(f"\n  Saved to {out2} ({len(xml2):,} bytes)")
            results.append((info2["shelf"], out2, info2))
        else:
            print("\n  FAILED: Could not download second deal EX-102")

        # Summary
        print("\n" + "=" * 60)
        print("DOWNLOAD SUMMARY")
        print("=" * 60)
        for shelf, path, info in results:
            print(f"  {shelf}: {path.name} ({info.get('size', 0):,} bytes)")
            print(f"    Filing: {info.get('accession', 'N/A')} ({info.get('filing_date', 'N/A')})")
            print(f"    URL: {info.get('ex102_url', 'N/A')}")

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())

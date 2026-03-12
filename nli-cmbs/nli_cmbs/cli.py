import asyncio

import typer
from rich.console import Console

app = typer.Typer(name="nli", help="NLI-CMBS CLI — CMBS portfolio intelligence tool")
console = Console()


@app.command()
def resolve(ticker: str = typer.Argument(..., help="Deal ticker, e.g. BMARK-2024-V6 or BBCMS-2023-C20")):
    """Resolve a CMBS deal ticker to its SEC EDGAR CIK number."""
    asyncio.run(_resolve(ticker))


async def _resolve(ticker: str) -> None:
    from nli_cmbs.db.session import async_session_factory
    from nli_cmbs.edgar.cik_resolver import CikResolver
    from nli_cmbs.edgar.client import EdgarClient

    client = EdgarClient()
    async with async_session_factory() as session:
        resolver = CikResolver(edgar_client=client, db_session=session)

        parsed = resolver.parse_ticker(ticker)
        if not parsed:
            console.print(f"[red]Could not parse ticker:[/red] {ticker}")
            raise typer.Exit(1)

        console.print(f"[bold]Resolving:[/bold] {parsed['normalized']}")
        console.print(f"  Shelf: {parsed['shelf']}  Year: {parsed['year']}  Series: {parsed['series']}")

        # Try each strategy and report which one worked
        result = await resolver.resolve_from_db(parsed["normalized"])
        if result:
            console.print("\n[green]Strategy 1 (DB lookup):[/green] Hit!")
            _print_mapping(result)
            await client.close()
            return

        console.print("[dim]Strategy 1 (DB lookup): miss[/dim]")

        result = await resolver.resolve_from_search(parsed["shelf"], parsed["year"], parsed["series"])
        if result:
            console.print("\n[green]Strategy 2 (EDGAR search):[/green] Hit!")
            _print_mapping(result)
            await client.close()
            return

        console.print("[dim]Strategy 2 (EDGAR search): miss[/dim]")

        result = await resolver.resolve_from_seed(parsed["shelf"], parsed["year"], parsed["series"])
        if result:
            console.print("\n[yellow]Strategy 3 (seed traversal):[/yellow] Hit (unverified)")
            _print_mapping(result)
            await client.close()
            return

        console.print("[dim]Strategy 3 (seed traversal): miss[/dim]")
        console.print("\n[red]All strategies failed.[/red] Could not resolve CIK.")

    await client.close()


def _print_mapping(mapping) -> None:
    console.print(f"  CIK:          {mapping.effective_cik}")
    console.print(f"  Depositor:    {mapping.depositor_cik}")
    if mapping.trust_cik:
        console.print(f"  Trust CIK:    {mapping.trust_cik}")
    console.print(f"  Trust name:   {mapping.trust_name}")
    console.print(f"  Shelf:        {mapping.issuer_shelf}")
    console.print(f"  Source:       {mapping.source}")
    console.print(f"  Verified:     {mapping.verified}")


@app.command(name="seed-cik-mappings")
def seed_cik_mappings():
    """Seed CIK mappings from CMBS_SHELVES seed data into the database."""
    asyncio.run(_seed_cik_mappings())


async def _seed_cik_mappings() -> None:
    from nli_cmbs.db.session import async_session_factory
    from nli_cmbs.edgar.client import EdgarClient
    from nli_cmbs.edgar.seed_data import CMBS_SHELVES

    client = EdgarClient()
    async with async_session_factory() as session:
        from sqlalchemy import select

        from nli_cmbs.db.models import CikMapping

        added = 0
        for shelf, info in CMBS_SHELVES.items():
            depositor_ciks = info["depositor_ciks"]

            for cik in depositor_ciks:
                # Check if this specific shelf+CIK combo already seeded
                stmt = select(CikMapping).where(
                    CikMapping.issuer_shelf == shelf,
                    CikMapping.depositor_cik == (cik.lstrip("0") or "0"),
                    CikMapping.source == "seed_depositor",
                )
                result = await session.execute(stmt)
                if result.scalar_one_or_none():
                    console.print(f"  [dim]{shelf} CIK {cik}: already seeded[/dim]")
                    continue

                # Verify CIK against EDGAR
                try:
                    submissions = await client.get_submissions(cik)
                    entity_name = submissions.get("name", "UNKNOWN")
                    console.print(f"  [green]{shelf}:[/green] CIK {cik} → {entity_name}")
                except Exception as e:
                    console.print(f"  [red]{shelf}:[/red] CIK {cik} verification failed: {e}")
                    entity_name = info["depositor_name"]

                suffix = f"-DEPOSITOR-{cik.lstrip('0')}" if len(depositor_ciks) > 1 else "-DEPOSITOR"
                mapping = CikMapping(
                    deal_ticker=f"{shelf}{suffix}",
                    trust_name=info["depositor_name"],
                    depositor_cik=cik.lstrip("0") or "0",
                    issuer_shelf=shelf,
                    depositor_name=info["depositor_name"],
                    verified=True,
                    source="seed_depositor",
                )
                session.add(mapping)
                added += 1

        await session.commit()
        console.print(f"\n[bold]Seeded {added} depositor-level entries.[/bold]")

    await client.close()


@app.command(name="fetch-filing")
def fetch_filing(ticker: str = typer.Argument(..., help="Deal ticker, e.g. BMARK-2024-V6")):
    """Fetch the latest ABS-EE filing for a CMBS deal."""
    asyncio.run(_fetch_filing(ticker))


async def _fetch_filing(ticker: str) -> None:
    from nli_cmbs.db.session import async_session_factory
    from nli_cmbs.edgar.cik_resolver import CikResolver
    from nli_cmbs.edgar.client import EdgarClient
    from nli_cmbs.edgar.filing_fetcher import FilingFetcher

    client = EdgarClient()
    async with async_session_factory() as session:
        resolver = CikResolver(edgar_client=client, db_session=session)
        mapping = await resolver.resolve(ticker)
        if not mapping:
            console.print(f"[red]Could not resolve CIK for:[/red] {ticker}")
            await client.close()
            raise typer.Exit(1)

        parsed = resolver.parse_ticker(ticker)
        normalized = parsed["normalized"] if parsed else ticker
        console.print(f"[bold]Fetching filing for:[/bold] {normalized} (CIK {mapping.effective_cik})")

        fetcher = FilingFetcher(edgar_client=client, db_session=session)
        filing = await fetcher.get_latest_filing(mapping.effective_cik, deal_ticker=normalized)
        if not filing:
            console.print("[red]No ABS-EE filing found.[/red]")
            await client.close()
            raise typer.Exit(1)

        console.print("\n[green]Filing found:[/green]")
        console.print(f"  Accession:    {filing.accession_number}")
        console.print(f"  Filing date:  {filing.filing_date}")
        console.print(f"  Form type:    {filing.form_type}")
        console.print(f"  EX-102 URL:   {filing.exhibit_url}")

    await client.close()


@app.command()
def scan(ticker: str = typer.Argument(..., help="Deal ticker, e.g. BMARK-2024-V6")):
    """Scan a CMBS deal — resolve CIK, fetch latest ABS-EE filing, download EX-102 XML."""
    asyncio.run(_scan(ticker))


async def _scan(ticker: str) -> None:
    from nli_cmbs.db.session import async_session_factory
    from nli_cmbs.edgar.cik_resolver import CikResolver
    from nli_cmbs.edgar.client import EdgarClient
    from nli_cmbs.edgar.filing_fetcher import FilingFetcher

    client = EdgarClient()
    try:
        async with async_session_factory() as session:
            # Step 1: Resolve CIK
            console.print(f"\n[bold]Step 1:[/bold] Resolving CIK for {ticker}...")
            resolver = CikResolver(edgar_client=client, db_session=session)
            mapping = await resolver.resolve(ticker)
            if not mapping:
                console.print(f"[red]Failed at Step 1:[/red] Could not resolve CIK for {ticker}")
                console.print("  Check that the ticker format is correct (e.g. BMARK-2024-V6)")
                raise typer.Exit(1)

            parsed = resolver.parse_ticker(ticker)
            normalized = parsed["normalized"] if parsed else ticker
            console.print(f"  [green]Resolved.[/green] CIK {mapping.effective_cik}")

            # Step 2: Fetch latest filing
            console.print("\n[bold]Step 2:[/bold] Fetching latest ABS-EE filing...")
            fetcher = FilingFetcher(edgar_client=client, db_session=session)
            filing = await fetcher.get_latest_filing(mapping.effective_cik, deal_ticker=normalized)
            if not filing:
                console.print("[red]Failed at Step 2:[/red] No ABS-EE filing found on EDGAR")
                console.print(f"  CIK {mapping.effective_cik} may not have ABS-EE filings, or EDGAR may be unavailable")
                raise typer.Exit(1)

            console.print(f"  [green]Found.[/green] {filing.accession_number} ({filing.filing_date})")

            # Step 3: Download EX-102 XML
            console.print("\n[bold]Step 3:[/bold] Downloading EX-102 XML...")
            try:
                xml_bytes = await fetcher.download_exhibit_102(filing)
            except Exception as e:
                console.print("[red]Failed at Step 3:[/red] Could not download EX-102 XML")
                console.print(f"  URL: {filing.exhibit_url}")
                console.print(f"  Error: {e}")
                raise typer.Exit(1)

            xml_size = len(xml_bytes)
            console.print(f"  [green]Downloaded.[/green] {xml_size:,} bytes")

            # Print summary
            console.print("\n" + "=" * 60)
            console.print(f"[bold]Deal:[/bold]           {normalized}")
            console.print(f"[bold]Trust:[/bold]          {mapping.trust_name}")
            console.print(f"[bold]CIK:[/bold]            {mapping.effective_cik}")
            if mapping.trust_cik and mapping.trust_cik != mapping.depositor_cik:
                console.print(f"[bold]Depositor CIK:[/bold]  {mapping.depositor_cik}")
            console.print(f"[bold]Latest Filing:[/bold]  {filing.filing_date} (accession: {filing.accession_number})")
            console.print(f"[bold]EX-102 URL:[/bold]     {filing.exhibit_url}")
            if xml_size >= 1_000_000:
                console.print(f"[bold]XML Size:[/bold]       {xml_size / 1_000_000:.1f} MB")
            else:
                console.print(f"[bold]XML Size:[/bold]       {xml_size / 1_000:.1f} KB")
            console.print("=" * 60)

            # Raw XML preview
            preview = xml_bytes[:500].decode("utf-8", errors="replace")
            console.print("\n[bold]Raw XML preview (first 500 chars):[/bold]")
            console.print(f"[dim]{preview}[/dim]")
    finally:
        await client.close()


@app.command()
def health():
    """Check API health."""
    import httpx

    r = httpx.get("http://localhost:8000/health")
    console.print(r.json())


if __name__ == "__main__":
    app()

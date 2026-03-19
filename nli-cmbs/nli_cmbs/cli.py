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
    """Scan a CMBS deal — full pipeline: resolve CIK, fetch filing, parse XML, persist to DB."""
    asyncio.run(_scan(ticker))


async def _scan(ticker: str) -> None:
    from rich.table import Table
    from sqlalchemy import func, select

    from nli_cmbs.db.models import Loan, LoanSnapshot
    from nli_cmbs.db.session import async_session_factory
    from nli_cmbs.services.deal_service import DealService

    async with async_session_factory() as session:
        console.print(f"\n[bold]Scanning deal:[/bold] {ticker}")
        svc = DealService(session)
        result = await svc.scan_deal(ticker)

        # Print IngestResult stats
        console.print("\n" + "=" * 60)
        console.print(f"[bold]Deal:[/bold]              {result.deal_ticker}")
        console.print(f"[bold]Filing:[/bold]            {result.filing_accession}")
        if result.reporting_period:
            console.print(f"[bold]Reporting Period:[/bold]  {result.reporting_period}")
        if result.already_parsed:
            console.print("[yellow]Already parsed — no new data ingested.[/yellow]")
        else:
            console.print(f"[bold]Loans Created:[/bold]     {result.loans_created}")
            console.print(f"[bold]Loans Updated:[/bold]     {result.loans_updated}")
            console.print(f"[bold]Snapshots Created:[/bold] {result.snapshots_created}")
            if result.parse_errors:
                console.print(f"[yellow]Parse Errors:[/yellow]      {result.parse_errors}")
        if result.errors:
            for err in result.errors[:5]:
                console.print(f"  [red]Error:[/red] {err}")
        console.print("=" * 60)

        # Query DB for summary
        deal = await svc.get_by_ticker(result.deal_ticker)
        if not deal:
            return

        # Total loans
        loan_count_result = await session.execute(
            select(func.count()).select_from(Loan).where(Loan.deal_id == deal.id)
        )
        total_loans = loan_count_result.scalar() or 0

        # Total UPB (sum of ending_balance from latest snapshots)
        upb_result = await session.execute(
            select(func.sum(LoanSnapshot.ending_balance)).where(
                LoanSnapshot.loan_id.in_(
                    select(Loan.id).where(Loan.deal_id == deal.id)
                )
            )
        )
        total_upb = upb_result.scalar() or 0

        # Delinquency counts
        delinq_result = await session.execute(
            select(LoanSnapshot.delinquency_status, func.count()).where(
                LoanSnapshot.loan_id.in_(
                    select(Loan.id).where(Loan.deal_id == deal.id)
                ),
                LoanSnapshot.delinquency_status.isnot(None),
                LoanSnapshot.delinquency_status != "",
            ).group_by(LoanSnapshot.delinquency_status)
        )
        delinq_counts = dict(delinq_result.all())

        console.print(f"\n[bold]Total Loans:[/bold]  {total_loans}")
        console.print(f"[bold]Total UPB:[/bold]    ${total_upb:,.2f}")
        if delinq_counts:
            console.print("[bold]Delinquency:[/bold]")
            for status, count in sorted(delinq_counts.items()):
                console.print(f"  {status}: {count}")

        # Top 5 loans by balance
        top_loans_result = await session.execute(
            select(Loan).where(Loan.deal_id == deal.id)
            .order_by(Loan.original_loan_amount.desc())
            .limit(5)
        )
        top_loans = list(top_loans_result.scalars().all())

        if top_loans:
            table = Table(title="Top 5 Loans by Balance")
            table.add_column("Loan ID", style="bold")
            table.add_column("Property Name")
            table.add_column("Borrower")
            table.add_column("Original Amount", justify="right")
            table.add_column("City, State")

            for loan in top_loans:
                amount = f"${loan.original_loan_amount:,.2f}" if loan.original_loan_amount else "-"
                location = f"{loan.property_city or '-'}, {loan.property_state or '-'}"
                table.add_row(
                    loan.prospectus_loan_id,
                    loan.property_name or "-",
                    loan.borrower_name or "-",
                    amount,
                    location,
                )

            console.print(table)


@app.command(name="parse-xml")
def parse_xml(filepath: str = typer.Argument(..., help="Path to EX-102 XML file")):
    """Parse an EX-102 XML file and display loan data."""
    from pathlib import Path

    from rich.table import Table

    from nli_cmbs.edgar.xml_parser import Ex102ParseError, Ex102Parser

    path = Path(filepath)
    if not path.exists():
        console.print(f"[red]File not found:[/red] {filepath}")
        raise typer.Exit(1)

    xml_bytes = path.read_bytes()
    parser = Ex102Parser()

    try:
        filing = parser.parse(xml_bytes)
    except Ex102ParseError as e:
        console.print(f"[red]Parse error:[/red] {e}")
        raise typer.Exit(1)

    console.print(f"\n[bold]Total loans parsed:[/bold] {filing.total_loan_count}")
    if filing.reporting_period_start:
        console.print(
            f"[bold]Reporting period:[/bold] {filing.reporting_period_start} to {filing.reporting_period_end}"
        )
    if filing.parse_errors:
        console.print(f"[yellow]Parse errors ({len(filing.parse_errors)}):[/yellow]")
        for err in filing.parse_errors[:5]:
            console.print(f"  - {err}")

    table = Table(title="First 5 Loans")
    table.add_column("ID", style="bold")
    table.add_column("Originator")
    table.add_column("Amount", justify="right")
    table.add_column("Maturity")
    table.add_column("Property")
    table.add_column("City, State")
    table.add_column("Type")

    for loan in filing.loans[:5]:
        amount = f"${loan.original_loan_amount:,.2f}" if loan.original_loan_amount else "-"
        maturity = str(loan.maturity_date) if loan.maturity_date else "-"
        location = f"{loan.property_city or '-'}, {loan.property_state or '-'}"
        table.add_row(
            loan.prospectus_loan_id,
            loan.originator_name or "-",
            amount,
            maturity,
            loan.property_name or "-",
            location,
            loan.property_type or "-",
        )

    console.print(table)


@app.command(name="report-all")
def report_all(
    output: str = typer.Option("reports", help="Output directory for report files"),
    regenerate: bool = typer.Option(False, help="Force regenerate even if cached"),
):
    """Generate surveillance reports for all ingested deals."""
    asyncio.run(_report_all(output, regenerate))


async def _report_all(output_dir: str, regenerate: bool) -> None:
    import time
    from pathlib import Path

    from nli_cmbs.ai.client import get_anthropic_client
    from nli_cmbs.db.session import async_session_factory
    from nli_cmbs.services.deal_service import DealService
    from nli_cmbs.services.report_service import ReportService

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    ai_client = get_anthropic_client()
    generated = 0
    failed = 0
    start = time.time()

    async with async_session_factory() as session:
        deal_service = DealService(session)
        deals = await deal_service.list_all()

        if not deals:
            console.print("[yellow]No deals found in database.[/yellow]")
            return

        console.print(f"[bold]Found {len(deals)} deals. Generating reports...[/bold]\n")

        service = ReportService(session, ai_client, deal_service)
        for deal in deals:
            ticker = deal.ticker
            console.print(f"  [{generated + failed + 1}/{len(deals)}] {ticker}...", end=" ")
            try:
                result = await service.generate_surveillance_report(ticker, regenerate=regenerate)
                # Save as markdown file
                filename = ticker.replace(" ", "_") + ".md"
                filepath = out_path / filename
                filepath.write_text(result.report_text)
                console.print(f"[green]OK[/green] → {filepath}")
                generated += 1
            except Exception as e:
                console.print(f"[red]FAILED[/red] — {e}")
                failed += 1

    elapsed = time.time() - start
    console.print(f"\n[bold]Summary:[/bold] {generated} generated, {failed} failed, {elapsed:.1f}s total")


@app.command()
def report(ticker: str = typer.Argument(..., help="Deal ticker, e.g. 'BMARK 2024-V6'")):
    """Generate a surveillance report for a CMBS deal."""
    asyncio.run(_report(ticker))


async def _report(ticker: str) -> None:
    from rich.markdown import Markdown
    from rich.panel import Panel

    from nli_cmbs.ai.client import get_anthropic_client
    from nli_cmbs.db.session import async_session_factory
    from nli_cmbs.services.deal_service import DealService
    from nli_cmbs.services.report_service import DealNotFoundError, ReportService

    ai_client = get_anthropic_client()
    async with async_session_factory() as session:
        service = ReportService(session, ai_client, DealService(session))
        try:
            console.print(f"\n[bold]Generating surveillance report for:[/bold] {ticker}")
            console.print("[dim]This may take 30-60 seconds on first run...[/dim]\n")
            result = await service.generate_surveillance_report(ticker)
        except DealNotFoundError:
            console.print(f"[red]Deal not found:[/red] {ticker}")
            raise typer.Exit(1)
        except Exception as e:
            console.print(f"[red]Report generation failed:[/red] {e}")
            raise typer.Exit(1)

    if result.cached:
        console.print("[yellow]Returned cached report[/yellow]\n")

    console.print(Panel(
        Markdown(result.report_text),
        title=f"Surveillance Report — {result.deal_ticker}",
        subtitle=f"Model: {result.model_used} | Filing: {result.filing_date} | Accession: {result.accession_number}",
    ))


@app.command(name="ingest-all")
def ingest_all(
    delay: float = typer.Option(1.0, help="Delay in seconds between EDGAR requests (SEC rate limit)"),
    limit: int = typer.Option(0, help="Max deals to ingest (0 = all)"),
    skip_parsed: bool = typer.Option(True, help="Skip deals that already have parsed filings"),
):
    """Bulk ingest all known deals from existing CIK mappings (Kaggle 2015-2023)."""
    asyncio.run(_ingest_all(delay, limit, skip_parsed))


async def _ingest_all(delay: float, limit: int, skip_parsed: bool) -> None:
    import time

    from sqlalchemy import select

    from nli_cmbs.db.models import CikMapping, Deal, Filing
    from nli_cmbs.db.session import async_session_factory
    from nli_cmbs.services.deal_service import DealService

    start = time.time()

    # ── Step 1: Load deal-level CIK mappings from DB ──
    console.print("[bold]Step 1:[/bold] Loading CIK mappings from DB...")
    deals_to_ingest: list[dict] = []
    seen_tickers: set[str] = set()

    async with async_session_factory() as session:
        stmt = select(CikMapping).where(
            CikMapping.source.notin_(["seed_depositor", "depositor_seed"])
        )
        result = await session.execute(stmt)
        db_mappings = list(result.scalars().all())

        for m in db_mappings:
            if m.deal_ticker in seen_tickers:
                continue
            if "-DEPOSITOR" in m.deal_ticker.upper():
                continue
            seen_tickers.add(m.deal_ticker)
            deals_to_ingest.append({
                "ticker": m.deal_ticker,
                "trust_name": m.trust_name,
            })

        console.print(f"  Found {len(deals_to_ingest)} deals from CIK mappings")

        # Filter out already-parsed deals
        parsed_tickers: set[str] = set()
        if skip_parsed:
            stmt = (
                select(Deal.ticker)
                .join(Filing, Filing.deal_id == Deal.id)
                .where(Filing.parsed.is_(True))
            )
            result = await session.execute(stmt)
            parsed_tickers = {row[0] for row in result.all()}

    deals_to_ingest.sort(key=lambda d: d["ticker"])
    if limit > 0:
        deals_to_ingest = deals_to_ingest[:limit]
        console.print(f"  Limited to first {limit} deals")

    to_ingest = [d for d in deals_to_ingest if d["ticker"] not in parsed_tickers]
    if parsed_tickers:
        console.print(
            f"  Skipping {len(deals_to_ingest) - len(to_ingest)} already-parsed deals"
        )
    console.print(f"  [bold]{len(to_ingest)} deals to ingest[/bold]\n")

    if not to_ingest:
        console.print("[yellow]Nothing to ingest.[/yellow]")
        return

    # ── Step 2: Run full pipeline for each deal ──
    console.print("[bold]Step 2:[/bold] Running ingest pipeline...\n")
    success, failed, skipped = 0, 0, 0
    errors_list: list[tuple[str, str]] = []

    for i, deal_info in enumerate(to_ingest):
        ticker = deal_info["ticker"]
        console.print(f"  [{i + 1}/{len(to_ingest)}] {ticker}...", end=" ")

        try:
            async with async_session_factory() as session:
                svc = DealService(session)
                result = await svc.scan_deal(ticker)

                if result.errors:
                    console.print(f"[red]FAILED[/red] — {result.errors[0]}")
                    errors_list.append((ticker, result.errors[0]))
                    failed += 1
                elif result.already_parsed:
                    console.print("[yellow]SKIP[/yellow] (already parsed)")
                    skipped += 1
                else:
                    console.print(
                        f"[green]OK[/green] — {result.loans_created} loans, "
                        f"{result.snapshots_created} snapshots"
                    )
                    success += 1
        except Exception as e:
            console.print(f"[red]ERROR[/red] — {e}")
            errors_list.append((ticker, str(e)))
            failed += 1

        if delay > 0:
            await asyncio.sleep(delay)

    elapsed = time.time() - start
    _print_ingest_summary(len(deals_to_ingest), success, skipped, failed, elapsed, errors_list)


@app.command(name="discover")
def discover(
    delay: float = typer.Option(1.5, help="Delay in seconds between EDGAR requests (SEC rate limit)"),
    limit: int = typer.Option(0, help="Max deals to ingest (0 = all)"),
    skip_parsed: bool = typer.Option(True, help="Skip deals that already have parsed filings"),
):
    """Discover and ingest new CMBS deals (2024+) from EDGAR depositor submissions."""
    asyncio.run(_discover(delay, limit, skip_parsed))


async def _discover(delay: float, limit: int, skip_parsed: bool) -> None:
    import re
    import time
    from collections import defaultdict

    from sqlalchemy import select

    from nli_cmbs.db.models import CikMapping, Deal, Filing
    from nli_cmbs.db.session import async_session_factory
    from nli_cmbs.edgar.client import EdgarClient
    from nli_cmbs.edgar.seed_data import CMBS_SHELVES
    from nli_cmbs.services.deal_service import DealService

    start = time.time()

    # Build regex patterns from seed data trust name patterns
    patterns: dict[str, tuple] = {}
    for shelf, info in CMBS_SHELVES.items():
        pattern = info["trust_name_pattern"]
        regex_str = (
            re.escape(pattern)
            .replace(r"\{year\}", r"(\d{4})")
            .replace(r"\{series\}", r"([A-Z0-9]+)")
        )
        patterns[shelf] = (re.compile(regex_str, re.IGNORECASE), info)

    # Load existing tickers to skip duplicates
    async with async_session_factory() as session:
        stmt = select(CikMapping.deal_ticker)
        result = await session.execute(stmt)
        existing_tickers = {row[0] for row in result.all()}

    console.print(f"  {len(existing_tickers)} deals already known in DB")

    # ── Step 1: Query depositor CIK submissions for ABS-EE filings ──
    console.print("\n[bold]Step 1:[/bold] Querying depositor CIKs for new ABS-EE filings...")

    cik_to_shelves: dict[str, list[str]] = defaultdict(list)
    for shelf, info in CMBS_SHELVES.items():
        for cik in info["depositor_ciks"]:
            cik_to_shelves[cik].append(shelf)

    unique_ciks = sorted(cik_to_shelves.keys())
    console.print(f"  Scanning {len(unique_ciks)} depositor CIKs...")

    # Group ABS-EE filings by fileNumber (each = a distinct deal registration)
    file_num_to_info: dict[str, dict] = {}

    client = EdgarClient()
    try:
        for cik in unique_ciks:
            try:
                subs = await client.get_submissions(cik)
            except Exception as e:
                console.print(f"  [red]CIK {cik}: {e}[/red]")
                await asyncio.sleep(delay)
                continue

            entity_name = subs.get("name", "")
            console.print(f"  [dim]CIK {cik}: {entity_name}[/dim]")

            recent = subs.get("filings", {}).get("recent", {})
            forms = recent.get("form", [])
            accessions = recent.get("accessionNumber", [])
            dates = recent.get("filingDate", [])
            file_numbers = recent.get("fileNumber", [])

            for i, form in enumerate(forms):
                if form != "ABS-EE":
                    continue
                fn = file_numbers[i] if i < len(file_numbers) else ""
                if not fn:
                    continue
                if fn not in file_num_to_info or dates[i] > file_num_to_info[fn]["date"]:
                    file_num_to_info[fn] = {
                        "depositor_cik": cik,
                        "accession": accessions[i],
                        "date": dates[i],
                        "entity_name": entity_name,
                    }

            await asyncio.sleep(delay)

        console.print(
            f"  Found {len(file_num_to_info)} deal registrations (file numbers)"
        )

        # ── Step 2: Resolve trust names from filing index pages ──
        console.print(
            "\n[bold]Step 2:[/bold] Resolving new deal names from filing indexes..."
        )
        discovered: list[dict] = []

        for fn, info in file_num_to_info.items():
            acc = info["accession"]
            dep_cik = info["depositor_cik"]

            try:
                trust_name, trust_cik = await _extract_trust_from_index(
                    client, dep_cik, acc
                )
            except Exception:
                console.print(f"  [dim]Could not read index for {acc}[/dim]")
                await asyncio.sleep(delay)
                continue

            if not trust_name:
                await asyncio.sleep(delay)
                continue

            # Match trust name against shelf patterns to derive ticker
            ticker = None
            matched_shelf = None
            for shelf, (regex, shelf_info) in patterns.items():
                m = regex.search(trust_name)
                if m:
                    year, series = m.group(1), m.group(2)
                    ticker = f"{shelf} {year}-{series}"
                    matched_shelf = shelf
                    break

            if not ticker or ticker in existing_tickers:
                await asyncio.sleep(delay)
                continue

            existing_tickers.add(ticker)
            discovered.append({
                "ticker": ticker,
                "trust_name": trust_name,
                "trust_cik": trust_cik or "",
                "shelf": matched_shelf,
                "depositor_cik": dep_cik.lstrip("0") or "0",
                "depositor_name": CMBS_SHELVES.get(matched_shelf, {}).get(
                    "depositor_name", ""
                ),
            })
            console.print(f"  [green]{ticker}[/green] ← {trust_name}")
            await asyncio.sleep(delay)

    finally:
        await client.close()

    discovered.sort(key=lambda d: d["ticker"])
    console.print(f"\n  [bold]Discovered {len(discovered)} new deals[/bold]")

    if not discovered:
        console.print("[yellow]No new deals found.[/yellow]")
        return

    if limit > 0:
        discovered = discovered[:limit]
        console.print(f"  Limited to first {limit} deals")

    # ── Step 3: Save CIK mappings and filter already-parsed ──
    console.print(f"\n[bold]Step 3:[/bold] Saving CIK mappings...")
    async with async_session_factory() as session:
        for d in discovered:
            stmt = select(CikMapping).where(
                CikMapping.deal_ticker.ilike(d["ticker"])
            )
            result = await session.execute(stmt)
            if not result.scalar_one_or_none():
                session.add(CikMapping(
                    deal_ticker=d["ticker"],
                    trust_name=d["trust_name"],
                    depositor_cik=d["depositor_cik"],
                    trust_cik=d["trust_cik"],
                    issuer_shelf=d["shelf"],
                    depositor_name=d["depositor_name"],
                    verified=True,
                    source="depositor_discovery",
                ))
        await session.commit()

        parsed_tickers: set[str] = set()
        if skip_parsed:
            stmt = (
                select(Deal.ticker)
                .join(Filing, Filing.deal_id == Deal.id)
                .where(Filing.parsed.is_(True))
            )
            result = await session.execute(stmt)
            parsed_tickers = {row[0] for row in result.all()}

    to_ingest = [d for d in discovered if d["ticker"] not in parsed_tickers]
    if parsed_tickers:
        console.print(
            f"  Skipping {len(discovered) - len(to_ingest)} already-parsed deals"
        )
    console.print(f"  [bold]{len(to_ingest)} new deals to ingest[/bold]\n")

    if not to_ingest:
        console.print("[yellow]All discovered deals already ingested.[/yellow]")
        return

    # ── Step 4: Run full pipeline for each deal ──
    console.print("[bold]Step 4:[/bold] Running ingest pipeline...\n")
    success, failed, skipped = 0, 0, 0
    errors_list: list[tuple[str, str]] = []

    for i, deal_info in enumerate(to_ingest):
        ticker = deal_info["ticker"]
        console.print(f"  [{i + 1}/{len(to_ingest)}] {ticker}...", end=" ")

        try:
            async with async_session_factory() as session:
                svc = DealService(session)
                result = await svc.scan_deal(ticker)

                if result.errors:
                    console.print(f"[red]FAILED[/red] — {result.errors[0]}")
                    errors_list.append((ticker, result.errors[0]))
                    failed += 1
                elif result.already_parsed:
                    console.print("[yellow]SKIP[/yellow] (already parsed)")
                    skipped += 1
                else:
                    console.print(
                        f"[green]OK[/green] — {result.loans_created} loans, "
                        f"{result.snapshots_created} snapshots"
                    )
                    success += 1
        except Exception as e:
            console.print(f"[red]ERROR[/red] — {e}")
            errors_list.append((ticker, str(e)))
            failed += 1

        if delay > 0:
            await asyncio.sleep(delay)

    elapsed = time.time() - start
    _print_ingest_summary(len(discovered), success, skipped, failed, elapsed, errors_list)


def _print_ingest_summary(
    total: int, success: int, skipped: int, failed: int,
    elapsed: float, errors_list: list[tuple[str, str]],
) -> None:
    console.print(f"\n{'=' * 60}")
    console.print("[bold]Ingest Summary[/bold]")
    console.print(f"  Total:       {total}")
    console.print(f"  Ingested:    {success}")
    console.print(f"  Skipped:     {skipped}")
    console.print(f"  Failed:      {failed}")
    console.print(f"  Time:        {elapsed:.1f}s")
    if errors_list:
        console.print(f"\n[red]Failures (showing first 20):[/red]")
        for ticker, err in errors_list[:20]:
            console.print(f"  {ticker}: {err}")
    console.print(f"{'=' * 60}")


async def _extract_trust_from_index(
    client, depositor_cik: str, accession: str
) -> tuple[str | None, str | None]:
    """Fetch a filing index page and extract the trust entity name and CIK.

    Returns (trust_name, trust_cik) or (None, None) if not found.
    """
    import re

    from lxml import html

    cik_num = str(int(depositor_cik))
    acc_no_dashes = accession.replace("-", "")
    index_url = (
        f"https://www.sec.gov/Archives/edgar/data/"
        f"{cik_num}/{acc_no_dashes}/{accession}-index.htm"
    )

    response = await client.download_filing_document(index_url)
    tree = html.fromstring(response)

    # The filing index page lists filers. Look for the trust entity
    # (the one that isn't the depositor, typically contains "Trust" in the name).
    text = tree.text_content()
    trust_name = None
    trust_cik = None

    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        # Look for lines like "Benchmark 2024-V6 Mortgage Trust  (Filer)"
        # or "BANK5 2024-5YR11 MORTGAGE TRUST  (Filer)"
        if "(filer)" in line.lower() and "trust" in line.lower():
            trust_name = re.sub(r"\s*\(Filer\)\s*$", "", line, flags=re.IGNORECASE).strip()
            break

    # Try to extract CIK from the page for the trust entity
    if trust_name:
        # Look for CIK link near the trust name
        for link in tree.xpath("//a[contains(@href, 'browse-edgar')]"):
            href = link.get("href", "")
            link_text = link.text_content().strip()
            if "CIK" in href and trust_name[:20].lower() in link_text.lower():
                m = re.search(r"CIK=(\d+)", href)
                if m:
                    trust_cik = m.group(1)
                break

    return trust_name, trust_cik


@app.command()
def backfill(
    years: int = typer.Option(3, help="Years of history to backfill"),
    limit: int = typer.Option(0, help="Limit number of deals to process (0 = all)"),
    deal: str = typer.Option("", help="Backfill single deal by ticker"),
):
    """Backfill historical filing data for time series analysis."""
    asyncio.run(_backfill(years, limit, deal))


async def _backfill(years: int, limit: int, deal_ticker: str) -> None:
    from sqlalchemy import select

    from nli_cmbs.db.models import Deal
    from nli_cmbs.db.session import async_session_factory
    from nli_cmbs.edgar.client import EdgarClient
    from nli_cmbs.edgar.filing_fetcher import FilingFetcher
    from nli_cmbs.edgar.xml_parser import Ex102Parser
    from nli_cmbs.services.backfill_service import BackfillService

    async with async_session_factory() as db:
        edgar = EdgarClient()
        try:
            fetcher = FilingFetcher(edgar_client=edgar, db_session=db)
            parser = Ex102Parser()

            service = BackfillService(
                db=db,
                edgar_client=edgar,
                filing_fetcher=fetcher,
                parser=parser,
                years_back=years,
            )

            if deal_ticker:
                # Single deal
                result = await db.execute(
                    select(Deal).where(Deal.ticker == deal_ticker)
                )
                deal_obj = result.scalar_one_or_none()
                if not deal_obj:
                    console.print(f"[red]Deal not found: {deal_ticker}[/red]")
                    return

                with console.status(f"Backfilling {deal_ticker}..."):
                    stats = await service.backfill_deal(deal_obj)

                console.print(f"\n[green]Backfill complete for {deal_ticker}[/green]")
                console.print(f"  Filings found: {stats.filings_found}")
                console.print(f"  Filings processed: {stats.filings_processed}")
                console.print(f"  Filings skipped (already parsed): {stats.filings_skipped}")
                console.print(f"  Loan snapshots created: {stats.loan_snapshots_created}")
                console.print(f"  Property snapshots created: {stats.property_snapshots_created}")
                if stats.errors:
                    console.print(f"  [yellow]Errors: {len(stats.errors)}[/yellow]")
                    for err in stats.errors[:5]:
                        console.print(f"    - {err}")
            else:
                # All deals
                backfill_result = await service.backfill_all_deals(
                    limit=limit if limit > 0 else None
                )

                console.print("\n[green]Backfill complete[/green]")
                console.print(f"  Deals processed: {backfill_result.deals_processed}")
                console.print(f"  Total filings: {backfill_result.total_filings}")
                console.print(f"  Loan snapshots: {backfill_result.total_loan_snapshots}")
                console.print(f"  Property snapshots: {backfill_result.total_property_snapshots}")
                console.print(f"  Errors: {len(backfill_result.errors)}")
        finally:
            await edgar.close()


@app.command(name="ingest-news")
def ingest_news(
    days: int = typer.Option(7, help="Ingest articles from last N days"),
    skip_full_text: bool = typer.Option(False, help="Skip fetching full article bodies"),
    skip_summaries: bool = typer.Option(False, help="Skip AI summary generation"),
    dry_run: bool = typer.Option(False, help="Show what would be ingested without saving"),
):
    """Ingest recent CMBS news articles from Trepp RSS feed."""
    asyncio.run(_ingest_news(days, skip_full_text, skip_summaries, dry_run))


async def _ingest_news(
    days: int, skip_full_text: bool, skip_summaries: bool, dry_run: bool,
) -> None:
    from nli_cmbs.services.news_ingestion import fetch_rss_feed

    console.print("[bold]Fetching Trepp CMBS RSS feed...[/bold]")
    articles = await fetch_rss_feed()

    from datetime import timedelta, timezone

    cutoff = __import__("datetime").datetime.now(timezone.utc) - timedelta(days=days)
    recent = [a for a in articles if a["published_date"] >= cutoff]
    console.print(f"Found {len(articles)} articles in feed, {len(recent)} from last {days} days")

    if not recent:
        console.print("[yellow]No recent articles to ingest.[/yellow]")
        return

    if dry_run:
        console.print(f"\n[bold]Dry run — would ingest up to {len(recent)} articles:[/bold]\n")
        for a in recent:
            date_str = a["published_date"].strftime("%Y-%m-%d")
            console.print(f'  "{a["title"]}" ({date_str})')
        return

    from nli_cmbs.ai.client import get_anthropic_client
    from nli_cmbs.db.session import async_session_factory
    from nli_cmbs.services.news_ingestion import ingest_new_articles

    ai_client = None if skip_summaries else get_anthropic_client()

    async with async_session_factory() as session:
        new_articles = await ingest_new_articles(
            db=session,
            since_days=days,
            fetch_full_text=not skip_full_text,
            generate_summaries=not skip_summaries,
            ai_client=ai_client,
        )

    if not new_articles:
        console.print("[yellow]All recent articles already in database.[/yellow]")
        return

    console.print(f"\n[green]Ingested {len(new_articles)} new articles from Trepp:[/green]\n")
    for a in new_articles:
        date_str = a.published_date.strftime("%Y-%m-%d")
        console.print(f'  [green]✓[/green] "{a.title}" ({date_str})')
        if a.key_themes:
            console.print(f"    Themes: {', '.join(a.key_themes)}")

    console.print(f"\nDone. Ingested {len(new_articles)} articles from Trepp.")


@app.command(name="list-news")
def list_news(
    limit: int = typer.Option(10, help="Number of articles to show"),
    source: str = typer.Option(None, help="Filter by source (e.g. Trepp)"),
    search: str = typer.Option(None, help="Search articles by title keyword"),
):
    """List recent news articles in the knowledge base."""
    asyncio.run(_list_news(limit, source, search))


async def _list_news(limit: int, source: str | None, search: str | None) -> None:
    from sqlalchemy import select

    from nli_cmbs.db.models import MarketArticle
    from nli_cmbs.db.session import async_session_factory

    async with async_session_factory() as session:
        stmt = (
            select(MarketArticle)
            .order_by(MarketArticle.published_date.desc())
            .limit(limit)
        )
        if source:
            stmt = stmt.where(MarketArticle.source == source)
        if search:
            stmt = stmt.where(MarketArticle.title.ilike(f"%{search}%"))

        result = await session.execute(stmt)
        articles = list(result.scalars().all())

    if not articles:
        console.print("[yellow]No articles found.[/yellow]")
        return

    from rich.table import Table

    table = Table(title=f"Market News ({len(articles)} articles)")
    table.add_column("Date", style="dim")
    table.add_column("Source")
    table.add_column("Title", max_width=60)
    table.add_column("Themes", max_width=40)

    for a in articles:
        date_str = a.published_date.strftime("%Y-%m-%d")
        themes = ", ".join(a.key_themes[:3]) if a.key_themes else "—"
        table.add_row(date_str, a.source, a.title, themes)

    console.print(table)


@app.command(name="news-digest")
def news_digest(
    days: int = typer.Option(7, help="Summarize articles from last N days"),
):
    """Generate a consolidated digest of recent CMBS news."""
    asyncio.run(_news_digest(days))


async def _news_digest(days: int) -> None:
    from rich.markdown import Markdown
    from rich.panel import Panel

    from nli_cmbs.ai.client import get_anthropic_client
    from nli_cmbs.db.session import async_session_factory
    from nli_cmbs.services.news_ingestion import generate_news_digest

    ai_client = get_anthropic_client()

    async with async_session_factory() as session:
        console.print(f"[bold]Generating digest from last {days} days...[/bold]\n")
        digest = await generate_news_digest(session, ai_client, days)

    console.print(Panel(
        Markdown(digest),
        title=f"CMBS Market Digest — Last {days} Days",
    ))


@app.command(name="hydrate-ground-truth")
def hydrate_ground_truth(
    deal: str = typer.Argument(..., help="Deal ticker, e.g. BMARK-2024-V6"),
    filing_id: str = typer.Option(None, help="Specific filing ID (default: latest parsed)"),
):
    """Hydrate ground truth entries from LoanSnapshot data for a deal."""
    asyncio.run(_hydrate_ground_truth(deal, filing_id))


async def _hydrate_ground_truth(ticker: str, filing_id: str | None) -> None:
    from sqlalchemy import select

    from nli_cmbs.db.models import Deal
    from nli_cmbs.db.session import async_session_factory
    from nli_cmbs.services.ground_truth_service import hydrate_ground_truth

    async with async_session_factory() as session:
        result = await session.execute(select(Deal).where(Deal.ticker == ticker))
        deal = result.scalar_one_or_none()
        if not deal:
            console.print(f"[red]Deal not found:[/red] {ticker}")
            raise typer.Exit(1)

        console.print(f"[bold]Hydrating ground truth for:[/bold] {ticker}")
        created = await hydrate_ground_truth(session, deal, filing_id=filing_id)
        console.print(f"[green]Created {created} ground truth entries.[/green]")


@app.command(name="eval-score")
def eval_score(
    deal: str = typer.Argument(..., help="Deal ticker to evaluate"),
):
    """Score AI extractions against ground truth for a deal."""
    asyncio.run(_eval_score(deal))


async def _eval_score(ticker: str) -> None:
    from sqlalchemy import select

    from nli_cmbs.db.models import Deal, GroundTruthEntry, LoanSnapshot
    from nli_cmbs.db.session import async_session_factory
    from nli_cmbs.services.scoring import score_extraction

    async with async_session_factory() as session:
        result = await session.execute(select(Deal).where(Deal.ticker == ticker))
        deal = result.scalar_one_or_none()
        if not deal:
            console.print(f"[red]Deal not found:[/red] {ticker}")
            raise typer.Exit(1)

        # Fetch ground truth entries
        gt_result = await session.execute(
            select(GroundTruthEntry).where(GroundTruthEntry.deal_id == deal.id)
        )
        gt_entries = list(gt_result.scalars().all())

        if not gt_entries:
            console.print(f"[yellow]No ground truth entries for {ticker}. Run hydrate-ground-truth first.[/yellow]")
            raise typer.Exit(1)

        # Build extracted values from latest snapshots
        snap_result = await session.execute(
            select(LoanSnapshot).where(
                LoanSnapshot.loan_id.in_([e.loan_id for e in gt_entries])
            )
        )
        snapshots = list(snap_result.scalars().all())

        # Group snapshots by loan_id, take latest
        latest_snaps: dict = {}
        for snap in snapshots:
            existing = latest_snaps.get(snap.loan_id)
            if not existing or snap.reporting_period_end_date > existing.reporting_period_end_date:
                latest_snaps[snap.loan_id] = snap

        # Build extracted values per loan
        from collections import defaultdict

        gt_by_loan: dict[str, list[dict]] = defaultdict(list)
        for entry in gt_entries:
            gt_by_loan[entry.loan_id].append({
                "field_name": entry.field_name,
                "field_value": entry.field_value,
                "field_type": entry.field_type,
                "tier": entry.tier,
            })

        total_scorecard = None
        loan_count = 0

        for loan_id, entries in gt_by_loan.items():
            snap = latest_snaps.get(loan_id)
            if not snap:
                continue

            extracted = {}
            for entry in entries:
                val = getattr(snap, entry["field_name"], None)
                extracted[entry["field_name"]] = str(val) if val is not None else None

            scorecard = score_extraction(entries, extracted)
            loan_count += 1

            if total_scorecard is None:
                total_scorecard = scorecard
            else:
                total_scorecard.total_fields += scorecard.total_fields
                total_scorecard.matched_fields += scorecard.matched_fields
                total_scorecard.missing_fields += scorecard.missing_fields
                total_scorecard.field_scores.extend(scorecard.field_scores)

        if total_scorecard is None:
            console.print("[yellow]No snapshots found to score against.[/yellow]")
            raise typer.Exit(1)

        total_scorecard.accuracy = (
            total_scorecard.matched_fields / total_scorecard.total_fields
            if total_scorecard.total_fields > 0 else 0.0
        )

        # Recompute tier accuracies
        tier_results: dict[int, list[bool]] = {1: [], 2: [], 3: []}
        errors: list[float] = []
        for fs in total_scorecard.field_scores:
            if fs.tier in tier_results:
                tier_results[fs.tier].append(fs.match)
            if fs.error is not None:
                errors.append(fs.error)

        t1 = tier_results.get(1, [])
        t2 = tier_results.get(2, [])
        total_scorecard.tier_1_accuracy = sum(t1) / len(t1) if t1 else None
        total_scorecard.tier_2_accuracy = sum(t2) / len(t2) if t2 else None
        total_scorecard.mean_absolute_error = sum(errors) / len(errors) if errors else None

        # Display results
        console.print(f"\n[bold]Evaluation Scorecard — {ticker}[/bold]")
        console.print(f"  Loans evaluated:  {loan_count}")
        console.print(f"  Total fields:     {total_scorecard.total_fields}")
        console.print(f"  Matched:          {total_scorecard.matched_fields}")
        console.print(f"  Missing:          {total_scorecard.missing_fields}")
        console.print(f"  [bold]Accuracy:       {total_scorecard.accuracy:.1%}[/bold]")
        if total_scorecard.tier_1_accuracy is not None:
            console.print(f"  Tier 1 accuracy:  {total_scorecard.tier_1_accuracy:.1%}")
        if total_scorecard.tier_2_accuracy is not None:
            console.print(f"  Tier 2 accuracy:  {total_scorecard.tier_2_accuracy:.1%}")
        if total_scorecard.mean_absolute_error is not None:
            console.print(f"  Mean abs error:   {total_scorecard.mean_absolute_error:.4f}")


@app.command()
def health():
    """Check API health."""
    import httpx

    r = httpx.get("http://localhost:8000/health")
    console.print(r.json())


if __name__ == "__main__":
    app()

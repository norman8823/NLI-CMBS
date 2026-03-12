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


@app.command()
def health():
    """Check API health."""
    import httpx

    r = httpx.get("http://localhost:8000/health")
    console.print(r.json())


if __name__ == "__main__":
    app()

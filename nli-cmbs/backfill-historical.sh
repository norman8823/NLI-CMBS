#!/bin/bash
# =============================================================================
# NLI-CMBS Historical Backfill — Overnight Ralph Script
# =============================================================================
#
# WHAT THIS DOES:
#   1. Creates property_snapshots table (if not exists)
#   2. Downloads 3 years of historical filings per deal
#   3. Parses each filing and creates loan_snapshots + property_snapshots
#   4. Validates with spot checks against EDGAR
#
# USAGE:
#   ./backfill-historical.sh
#
# EXPECTED RUNTIME: 4-6 hours
# =============================================================================

set -euo pipefail

PROJECT_DIR="${NLI_CMBS_DIR:-$(pwd)}"
LOG_DIR="$PROJECT_DIR/.claude/backfill-logs"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$LOG_DIR"
cd "$PROJECT_DIR"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() { echo -e "${GREEN}[$(date +%H:%M:%S)]${NC} $1"; }
warn() { echo -e "${YELLOW}[$(date +%H:%M:%S)] WARNING:${NC} $1"; }
fail() { echo -e "${RED}[$(date +%H:%M:%S)] FAILED:${NC} $1"; }

# =============================================================================
# PHASE 1: Schema Migration
# =============================================================================

read -r -d '' PHASE1_PROMPT << 'EOF' || true
In the nli-cmbs project, create a database migration to add the property_snapshots table for historical tracking.

TASK:
1. Generate an Alembic migration that creates the property_snapshots table:
```python
# In the upgrade() function:
op.create_table(
    'property_snapshots',
    sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
    sa.Column('property_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('properties.id', ondelete='CASCADE'), nullable=False),
    sa.Column('filing_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('filings.id', ondelete='CASCADE'), nullable=False),
    sa.Column('reporting_period_end', sa.Date, nullable=False),
    
    # Financials
    sa.Column('occupancy', sa.Numeric(7, 4), nullable=True),
    sa.Column('noi', sa.Numeric(20, 2), nullable=True),
    sa.Column('ncf', sa.Numeric(20, 2), nullable=True),
    sa.Column('revenue', sa.Numeric(20, 2), nullable=True),
    sa.Column('operating_expenses', sa.Numeric(20, 2), nullable=True),
    sa.Column('dscr_noi', sa.Numeric(10, 4), nullable=True),
    sa.Column('dscr_ncf', sa.Numeric(10, 4), nullable=True),
    
    # Valuation
    sa.Column('valuation_amount', sa.Numeric(20, 2), nullable=True),
    sa.Column('valuation_date', sa.Date, nullable=True),
    sa.Column('valuation_source', sa.String(50), nullable=True),
    
    sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()'), nullable=False),
    
    sa.UniqueConstraint('property_id', 'filing_id', name='uq_property_snapshots_property_filing')
)

op.create_index('idx_property_snapshots_property_id', 'property_snapshots', ['property_id'])
op.create_index('idx_property_snapshots_filing_id', 'property_snapshots', ['filing_id'])
op.create_index('idx_property_snapshots_period', 'property_snapshots', ['reporting_period_end'])
```

2. Add the PropertySnapshot model to nli_cmbs/db/models.py:
```python
class PropertySnapshot(Base):
    __tablename__ = "property_snapshots"
    
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    property_id = Column(UUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"), nullable=False)
    filing_id = Column(UUID(as_uuid=True), ForeignKey("filings.id", ondelete="CASCADE"), nullable=False)
    reporting_period_end = Column(Date, nullable=False)
    
    # Financials
    occupancy = Column(Numeric(7, 4))
    noi = Column(Numeric(20, 2))
    ncf = Column(Numeric(20, 2))
    revenue = Column(Numeric(20, 2))
    operating_expenses = Column(Numeric(20, 2))
    dscr_noi = Column(Numeric(10, 4))
    dscr_ncf = Column(Numeric(10, 4))
    
    # Valuation
    valuation_amount = Column(Numeric(20, 2))
    valuation_date = Column(Date)
    valuation_source = Column(String(50))
    
    created_at = Column(DateTime, server_default=text("NOW()"), nullable=False)
    
    # Relationships
    property = relationship("Property", back_populates="snapshots")
    filing = relationship("Filing", back_populates="property_snapshots")
    
    __table_args__ = (
        UniqueConstraint('property_id', 'filing_id', name='uq_property_snapshots_property_filing'),
    )
```

3. Update the Property model to add the relationship:
```python
# In Property class, add:
snapshots = relationship("PropertySnapshot", back_populates="property", cascade="all, delete-orphan")
```

4. Update the Filing model to add the relationship:
```python
# In Filing class, add:
property_snapshots = relationship("PropertySnapshot", back_populates="filing", cascade="all, delete-orphan")
```

VERIFICATION:
1. alembic upgrade head succeeds
2. \d property_snapshots shows all columns with correct types
3. Foreign keys to properties and filings exist
4. Unique constraint on (property_id, filing_id) exists
5. ruff check . passes

When complete, output: PHASE1_COMPLETE
EOF

# =============================================================================
# PHASE 2: Backfill Service
# =============================================================================

read -r -d '' PHASE2_PROMPT << 'EOF' || true
In the nli-cmbs project, create a backfill service that downloads historical filings and creates snapshots.

TASK:
1. Create nli_cmbs/services/backfill_service.py:
```python
from dataclasses import dataclass
from datetime import date, timedelta
import asyncio
from typing import Optional
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from nli_cmbs.db.models import Deal, Filing, Loan, LoanSnapshot, Property, PropertySnapshot
from nli_cmbs.edgar.client import EdgarClient
from nli_cmbs.edgar.filing_fetcher import FilingFetcher
from nli_cmbs.edgar.xml_parser import Ex102Parser

logger = logging.getLogger(__name__)


@dataclass
class BackfillStats:
    deal_ticker: str
    filings_found: int
    filings_processed: int
    filings_skipped: int  # already parsed
    loan_snapshots_created: int
    property_snapshots_created: int
    errors: list[str]


@dataclass 
class BackfillResult:
    deals_processed: int
    total_filings: int
    total_loan_snapshots: int
    total_property_snapshots: int
    errors: list[str]
    stats_by_deal: list[BackfillStats]


class BackfillService:
    def __init__(
        self, 
        db: AsyncSession, 
        edgar_client: EdgarClient,
        filing_fetcher: FilingFetcher,
        parser: Ex102Parser,
        years_back: int = 3,
        rate_limit_delay: float = 0.5  # seconds between EDGAR requests
    ):
        self.db = db
        self.edgar = edgar_client
        self.filing_fetcher = filing_fetcher
        self.parser = parser
        self.years_back = years_back
        self.rate_limit_delay = rate_limit_delay
    
    async def backfill_all_deals(self, limit: Optional[int] = None) -> BackfillResult:
        """Backfill historical data for all deals in the database."""
        
        # Get all deals
        query = select(Deal).order_by(Deal.ticker)
        if limit:
            query = query.limit(limit)
        result = await self.db.execute(query)
        deals = result.scalars().all()
        
        total_result = BackfillResult(
            deals_processed=0,
            total_filings=0,
            total_loan_snapshots=0,
            total_property_snapshots=0,
            errors=[],
            stats_by_deal=[]
        )
        
        for deal in deals:
            try:
                stats = await self.backfill_deal(deal)
                total_result.stats_by_deal.append(stats)
                total_result.deals_processed += 1
                total_result.total_filings += stats.filings_processed
                total_result.total_loan_snapshots += stats.loan_snapshots_created
                total_result.total_property_snapshots += stats.property_snapshots_created
                total_result.errors.extend(stats.errors)
                
                logger.info(f"Completed {deal.ticker}: {stats.filings_processed} filings, "
                           f"{stats.loan_snapshots_created} loan snapshots, "
                           f"{stats.property_snapshots_created} property snapshots")
                
            except Exception as e:
                error_msg = f"Failed to backfill {deal.ticker}: {str(e)}"
                logger.error(error_msg)
                total_result.errors.append(error_msg)
        
        return total_result
    
    async def backfill_deal(self, deal: Deal) -> BackfillStats:
        """Backfill historical filings for a single deal."""
        
        stats = BackfillStats(
            deal_ticker=deal.ticker,
            filings_found=0,
            filings_processed=0,
            filings_skipped=0,
            loan_snapshots_created=0,
            property_snapshots_created=0,
            errors=[]
        )
        
        # Get CIK (prefer trust_cik, fall back to depositor_cik)
        cik = deal.trust_cik or deal.depositor_cik
        if not cik:
            stats.errors.append(f"No CIK found for {deal.ticker}")
            return stats
        
        # Calculate date range
        cutoff_date = date.today() - timedelta(days=365 * self.years_back)
        
        # Fetch all ABS-EE filings for this CIK
        try:
            filings_metadata = await self.filing_fetcher.get_filings_history(
                cik=cik, 
                since_date=cutoff_date,
                limit=100  # ~3 years of monthly filings
            )
            stats.filings_found = len(filings_metadata)
        except Exception as e:
            stats.errors.append(f"Failed to fetch filing history: {str(e)}")
            return stats
        
        # Process each filing
        for filing_meta in filings_metadata:
            await asyncio.sleep(self.rate_limit_delay)  # Rate limiting
            
            try:
                # Check if already processed
                existing = await self.db.execute(
                    select(Filing).where(Filing.accession_number == filing_meta.accession_number)
                )
                filing = existing.scalar_one_or_none()
                
                if filing and filing.parsed:
                    stats.filings_skipped += 1
                    continue
                
                # Create or get filing record
                if not filing:
                    filing = Filing(
                        deal_id=deal.id,
                        accession_number=filing_meta.accession_number,
                        filing_date=filing_meta.filing_date,
                        form_type="ABS-EE",
                        exhibit_url=filing_meta.exhibit_url,
                        parsed=False
                    )
                    self.db.add(filing)
                    await self.db.flush()
                
                # Download and parse XML
                xml_bytes = await self.edgar.download_filing_document(filing_meta.exhibit_url)
                parsed = self.parser.parse(xml_bytes)
                
                # Update filing with reporting period
                filing.reporting_period_start = parsed.reporting_period_start
                filing.reporting_period_end = parsed.reporting_period_end
                
                # Create snapshots
                loan_count, prop_count = await self._create_snapshots(deal, filing, parsed)
                stats.loan_snapshots_created += loan_count
                stats.property_snapshots_created += prop_count
                
                # Mark filing as parsed
                filing.parsed = True
                await self.db.commit()
                
                stats.filings_processed += 1
                
            except Exception as e:
                stats.errors.append(f"Filing {filing_meta.accession_number}: {str(e)}")
                await self.db.rollback()
        
        return stats
    
    async def _create_snapshots(self, deal: Deal, filing: Filing, parsed) -> tuple[int, int]:
        """Create loan and property snapshots from parsed data. Returns (loan_count, property_count)."""
        
        loan_count = 0
        prop_count = 0
        
        for parsed_loan in parsed.loans:
            # Find or skip loan
            loan_result = await self.db.execute(
                select(Loan).where(
                    Loan.deal_id == deal.id,
                    Loan.prospectus_loan_id == parsed_loan.prospectus_loan_id
                )
            )
            loan = loan_result.scalar_one_or_none()
            
            if not loan:
                # Loan doesn't exist yet - this is a historical filing before our initial ingest
                # Skip for now - we only create snapshots for loans we already know about
                continue
            
            # Check for existing loan snapshot
            existing_snap = await self.db.execute(
                select(LoanSnapshot).where(
                    LoanSnapshot.loan_id == loan.id,
                    LoanSnapshot.filing_id == filing.id
                )
            )
            if existing_snap.scalar_one_or_none():
                continue  # Already exists
            
            # Create loan snapshot
            loan_snapshot = LoanSnapshot(
                loan_id=loan.id,
                filing_id=filing.id,
                reporting_period_begin_date=parsed.reporting_period_start,
                reporting_period_end_date=parsed.reporting_period_end,
                beginning_balance=parsed_loan.beginning_balance,
                ending_balance=parsed_loan.ending_balance,
                current_interest_rate=parsed_loan.current_interest_rate,
                scheduled_interest_amount=parsed_loan.scheduled_interest_amount,
                scheduled_principal_amount=parsed_loan.scheduled_principal_amount,
                actual_interest_collected=parsed_loan.actual_interest_collected,
                actual_principal_collected=parsed_loan.actual_principal_collected,
                actual_other_collected=parsed_loan.actual_other_collected,
                servicer_advanced_amount=parsed_loan.servicer_advanced_amount,
                delinquency_status=parsed_loan.delinquency_status,
                interest_paid_through_date=parsed_loan.interest_paid_through_date,
                next_payment_amount_due=parsed_loan.next_payment_amount_due,
            )
            self.db.add(loan_snapshot)
            loan_count += 1
            
            # Create property snapshots for this loan
            for parsed_prop in parsed_loan.properties:
                # Find existing property
                prop_result = await self.db.execute(
                    select(Property).where(
                        Property.loan_id == loan.id,
                        Property.property_id == parsed_prop.property_id
                    )
                )
                prop = prop_result.scalar_one_or_none()
                
                if not prop:
                    continue  # Property doesn't exist
                
                # Check for existing property snapshot
                existing_prop_snap = await self.db.execute(
                    select(PropertySnapshot).where(
                        PropertySnapshot.property_id == prop.id,
                        PropertySnapshot.filing_id == filing.id
                    )
                )
                if existing_prop_snap.scalar_one_or_none():
                    continue
                
                # Create property snapshot
                prop_snapshot = PropertySnapshot(
                    property_id=prop.id,
                    filing_id=filing.id,
                    reporting_period_end=parsed.reporting_period_end,
                    occupancy=parsed_prop.occupancy_most_recent or parsed_prop.occupancy_securitization,
                    noi=parsed_prop.noi_most_recent or parsed_prop.noi_securitization,
                    ncf=parsed_prop.ncf_most_recent or parsed_prop.ncf_securitization,
                    revenue=parsed_prop.revenue_most_recent,
                    operating_expenses=parsed_prop.operating_expenses_most_recent,
                    dscr_noi=parsed_prop.dscr_noi_most_recent or parsed_prop.dscr_noi_securitization,
                    dscr_ncf=parsed_prop.dscr_ncf_most_recent or parsed_prop.dscr_ncf_securitization,
                    valuation_amount=parsed_prop.valuation_most_recent or parsed_prop.valuation_securitization,
                    valuation_date=parsed_prop.valuation_most_recent_date,
                    valuation_source=parsed_prop.valuation_source,
                )
                self.db.add(prop_snapshot)
                prop_count += 1
        
        return loan_count, prop_count
```

2. Add CLI command for backfill in nli_cmbs/cli.py:
```python
@app.command()
def backfill(
    years: int = typer.Option(3, help="Years of history to backfill"),
    limit: int = typer.Option(None, help="Limit number of deals to process"),
    deal: str = typer.Option(None, help="Backfill single deal by ticker"),
):
    """Backfill historical filing data for time series analysis."""
    import asyncio
    from rich.console import Console
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn
    
    console = Console()
    
    async def run_backfill():
        async with get_session() as db:
            edgar = EdgarClient()
            fetcher = FilingFetcher(edgar, db)
            parser = Ex102Parser()
            
            service = BackfillService(
                db=db,
                edgar_client=edgar,
                filing_fetcher=fetcher,
                parser=parser,
                years_back=years,
            )
            
            if deal:
                # Single deal
                deal_obj = await db.execute(select(Deal).where(Deal.ticker == deal))
                deal_obj = deal_obj.scalar_one_or_none()
                if not deal_obj:
                    console.print(f"[red]Deal not found: {deal}[/red]")
                    return
                
                with console.status(f"Backfilling {deal}..."):
                    stats = await service.backfill_deal(deal_obj)
                
                console.print(f"\n[green]Backfill complete for {deal}[/green]")
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
                result = await service.backfill_all_deals(limit=limit)
                
                console.print(f"\n[green]Backfill complete[/green]")
                console.print(f"  Deals processed: {result.deals_processed}")
                console.print(f"  Total filings: {result.total_filings}")
                console.print(f"  Loan snapshots: {result.total_loan_snapshots}")
                console.print(f"  Property snapshots: {result.total_property_snapshots}")
                console.print(f"  Errors: {len(result.errors)}")
    
    asyncio.run(run_backfill())
```

VERIFICATION:
1. python -m nli_cmbs.cli backfill --deal "BMARK 2024-V6" --years 1 completes without error
2. Query shows multiple loan_snapshots per loan:
   SELECT l.prospectus_loan_id, COUNT(ls.id) FROM loans l 
   JOIN loan_snapshots ls ON ls.loan_id = l.id 
   WHERE l.deal_id = (SELECT id FROM deals WHERE ticker = 'BMARK 2024-V6')
   GROUP BY l.id HAVING COUNT(ls.id) > 1;
3. Query shows property_snapshots created:
   SELECT COUNT(*) FROM property_snapshots;
4. ruff check . passes

When complete, output: PHASE2_COMPLETE
EOF

# =============================================================================
# PHASE 3: Validation Service
# =============================================================================

read -r -d '' PHASE3_PROMPT << 'EOF' || true
In the nli-cmbs project, create a validation service that spot-checks backfilled data against EDGAR.

TASK:
1. Create nli_cmbs/services/validation_service.py:
```python
from dataclasses import dataclass
from decimal import Decimal
import logging
from typing import Optional
import random

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from nli_cmbs.db.models import Deal, Filing, Loan, LoanSnapshot, Property, PropertySnapshot
from nli_cmbs.edgar.client import EdgarClient
from nli_cmbs.edgar.xml_parser import Ex102Parser

logger = logging.getLogger(__name__)


@dataclass
class ValidationCheck:
    deal_ticker: str
    filing_accession: str
    loan_id: str
    field: str
    db_value: Optional[str]
    edgar_value: Optional[str]
    match: bool
    tolerance_used: Optional[float] = None


@dataclass
class ValidationResult:
    checks_performed: int
    checks_passed: int
    checks_failed: int
    checks: list[ValidationCheck]
    
    @property
    def pass_rate(self) -> float:
        if self.checks_performed == 0:
            return 0.0
        return self.checks_passed / self.checks_performed


class ValidationService:
    """Spot-check database values against EDGAR source data."""
    
    NUMERIC_TOLERANCE = 0.01  # 1% tolerance for numeric comparisons
    
    def __init__(
        self,
        db: AsyncSession,
        edgar_client: EdgarClient,
        parser: Ex102Parser,
    ):
        self.db = db
        self.edgar = edgar_client
        self.parser = parser
    
    async def validate_random_sample(
        self, 
        sample_size: int = 10,
        fields_to_check: list[str] = None
    ) -> ValidationResult:
        """Validate a random sample of loan snapshots against EDGAR."""
        
        if fields_to_check is None:
            fields_to_check = ['ending_balance', 'delinquency_status', 'current_interest_rate']
        
        result = ValidationResult(
            checks_performed=0,
            checks_passed=0,
            checks_failed=0,
            checks=[]
        )
        
        # Get random sample of loan snapshots with their filings
        query = select(LoanSnapshot, Loan, Filing, Deal).join(
            Loan, LoanSnapshot.loan_id == Loan.id
        ).join(
            Filing, LoanSnapshot.filing_id == Filing.id
        ).join(
            Deal, Loan.deal_id == Deal.id
        ).order_by(func.random()).limit(sample_size)
        
        rows = await self.db.execute(query)
        samples = rows.all()
        
        for snapshot, loan, filing, deal in samples:
            try:
                checks = await self._validate_snapshot(snapshot, loan, filing, deal, fields_to_check)
                for check in checks:
                    result.checks.append(check)
                    result.checks_performed += 1
                    if check.match:
                        result.checks_passed += 1
                    else:
                        result.checks_failed += 1
            except Exception as e:
                logger.error(f"Validation failed for {deal.ticker}/{loan.prospectus_loan_id}: {e}")
        
        return result
    
    async def validate_deal(self, deal_ticker: str, sample_size: int = 5) -> ValidationResult:
        """Validate a sample of snapshots from a specific deal."""
        
        result = ValidationResult(
            checks_performed=0,
            checks_passed=0,
            checks_failed=0,
            checks=[]
        )
        
        # Get deal
        deal_result = await self.db.execute(select(Deal).where(Deal.ticker == deal_ticker))
        deal = deal_result.scalar_one_or_none()
        if not deal:
            return result
        
        # Get random filings for this deal
        query = select(Filing).where(
            Filing.deal_id == deal.id,
            Filing.parsed == True
        ).order_by(func.random()).limit(sample_size)
        
        filings = (await self.db.execute(query)).scalars().all()
        
        for filing in filings:
            # Get a random loan snapshot from this filing
            snap_query = select(LoanSnapshot, Loan).join(
                Loan, LoanSnapshot.loan_id == Loan.id
            ).where(
                LoanSnapshot.filing_id == filing.id
            ).order_by(func.random()).limit(1)
            
            row = (await self.db.execute(snap_query)).first()
            if not row:
                continue
            
            snapshot, loan = row
            
            try:
                checks = await self._validate_snapshot(
                    snapshot, loan, filing, deal,
                    ['ending_balance', 'delinquency_status']
                )
                for check in checks:
                    result.checks.append(check)
                    result.checks_performed += 1
                    if check.match:
                        result.checks_passed += 1
                    else:
                        result.checks_failed += 1
            except Exception as e:
                logger.error(f"Validation error: {e}")
        
        return result
    
    async def _validate_snapshot(
        self,
        snapshot: LoanSnapshot,
        loan: Loan,
        filing: Filing,
        deal: Deal,
        fields: list[str]
    ) -> list[ValidationCheck]:
        """Validate a single snapshot against EDGAR source."""
        
        checks = []
        
        # Download and parse the original XML
        xml_bytes = await self.edgar.download_filing_document(filing.exhibit_url)
        parsed = self.parser.parse(xml_bytes)
        
        # Find the matching loan in parsed data
        edgar_loan = None
        for pl in parsed.loans:
            if pl.prospectus_loan_id == loan.prospectus_loan_id:
                edgar_loan = pl
                break
        
        if not edgar_loan:
            # Loan not found in EDGAR - might be okay if loan was added later
            return checks
        
        # Check each field
        for field in fields:
            db_val = getattr(snapshot, field, None)
            edgar_val = getattr(edgar_loan, field, None)
            
            match = self._values_match(db_val, edgar_val)
            
            checks.append(ValidationCheck(
                deal_ticker=deal.ticker,
                filing_accession=filing.accession_number,
                loan_id=loan.prospectus_loan_id,
                field=field,
                db_value=str(db_val) if db_val is not None else None,
                edgar_value=str(edgar_val) if edgar_val is not None else None,
                match=match,
                tolerance_used=self.NUMERIC_TOLERANCE if isinstance(db_val, (int, float, Decimal)) else None
            ))
        
        return checks
    
    def _values_match(self, db_val, edgar_val) -> bool:
        """Compare two values with appropriate tolerance."""
        
        if db_val is None and edgar_val is None:
            return True
        if db_val is None or edgar_val is None:
            return False
        
        # Numeric comparison with tolerance
        if isinstance(db_val, (int, float, Decimal)) and isinstance(edgar_val, (int, float, Decimal)):
            if float(edgar_val) == 0:
                return float(db_val) == 0
            diff = abs(float(db_val) - float(edgar_val)) / abs(float(edgar_val))
            return diff <= self.NUMERIC_TOLERANCE
        
        # String comparison (case-insensitive, strip whitespace)
        return str(db_val).strip().lower() == str(edgar_val).strip().lower()
```

2. Add CLI command for validation:
```python
@app.command()
def validate(
    deal: str = typer.Option(None, help="Validate specific deal"),
    sample_size: int = typer.Option(10, help="Number of snapshots to check"),
):
    """Spot-check backfilled data against EDGAR source."""
    import asyncio
    from rich.console import Console
    from rich.table import Table
    
    console = Console()
    
    async def run_validation():
        async with get_session() as db:
            edgar = EdgarClient()
            parser = Ex102Parser()
            
            service = ValidationService(db, edgar, parser)
            
            if deal:
                result = await service.validate_deal(deal, sample_size)
            else:
                result = await service.validate_random_sample(sample_size)
            
            # Display results
            console.print(f"\n[bold]Validation Results[/bold]")
            console.print(f"  Checks performed: {result.checks_performed}")
            console.print(f"  Passed: [green]{result.checks_passed}[/green]")
            console.print(f"  Failed: [red]{result.checks_failed}[/red]")
            console.print(f"  Pass rate: {result.pass_rate:.1%}")
            
            if result.checks_failed > 0:
                console.print(f"\n[yellow]Failed checks:[/yellow]")
                table = Table()
                table.add_column("Deal")
                table.add_column("Loan")
                table.add_column("Field")
                table.add_column("DB Value")
                table.add_column("EDGAR Value")
                
                for check in result.checks:
                    if not check.match:
                        table.add_row(
                            check.deal_ticker,
                            check.loan_id,
                            check.field,
                            check.db_value or "NULL",
                            check.edgar_value or "NULL"
                        )
                
                console.print(table)
            
            # Exit with error if pass rate is below threshold
            if result.pass_rate < 0.95:
                console.print(f"\n[red]WARNING: Pass rate below 95% threshold[/red]")
                raise typer.Exit(1)
            else:
                console.print(f"\n[green]Validation passed![/green]")
    
    asyncio.run(run_validation())
```

VERIFICATION:
1. python -m nli_cmbs.cli validate --sample-size 5 completes
2. Pass rate is >= 95%
3. Any failures are logged with details
4. ruff check . passes

When complete, output: PHASE3_COMPLETE
EOF

# =============================================================================
# PHASE 4: API Endpoint for Property History
# =============================================================================

read -r -d '' PHASE4_PROMPT << 'EOF' || true
In the nli-cmbs project, add an API endpoint to retrieve property snapshot history for sparkline charts.

TASK:
1. Add endpoint in nli_cmbs/api/endpoints/properties.py:
```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from nli_cmbs.db.session import get_db
from nli_cmbs.db.models import Property, PropertySnapshot
from nli_cmbs.schemas.property import PropertyHistoryResponse, PropertySnapshotSchema

router = APIRouter(prefix="/properties", tags=["properties"])


@router.get("/{property_id}/history", response_model=PropertyHistoryResponse)
async def get_property_history(
    property_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get historical snapshots for a property (for sparkline charts)."""
    
    # Verify property exists
    prop = await db.get(Property, property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    
    # Get snapshots ordered by date
    query = select(PropertySnapshot).where(
        PropertySnapshot.property_id == property_id
    ).order_by(PropertySnapshot.reporting_period_end.asc())
    
    result = await db.execute(query)
    snapshots = result.scalars().all()
    
    return PropertyHistoryResponse(
        property_id=property_id,
        property_name=prop.property_name,
        snapshot_count=len(snapshots),
        snapshots=[
            PropertySnapshotSchema(
                reporting_period_end=s.reporting_period_end,
                occupancy=float(s.occupancy) if s.occupancy else None,
                noi=float(s.noi) if s.noi else None,
                ncf=float(s.ncf) if s.ncf else None,
                dscr_noi=float(s.dscr_noi) if s.dscr_noi else None,
                dscr_ncf=float(s.dscr_ncf) if s.dscr_ncf else None,
                valuation_amount=float(s.valuation_amount) if s.valuation_amount else None,
            )
            for s in snapshots
        ]
    )
```

2. Add Pydantic schemas in nli_cmbs/schemas/property.py:
```python
from pydantic import BaseModel
from datetime import date
from uuid import UUID
from typing import Optional


class PropertySnapshotSchema(BaseModel):
    reporting_period_end: date
    occupancy: Optional[float] = None
    noi: Optional[float] = None
    ncf: Optional[float] = None
    dscr_noi: Optional[float] = None
    dscr_ncf: Optional[float] = None
    valuation_amount: Optional[float] = None


class PropertyHistoryResponse(BaseModel):
    property_id: UUID
    property_name: Optional[str]
    snapshot_count: int
    snapshots: list[PropertySnapshotSchema]
```

3. Register the router in nli_cmbs/api/router.py

VERIFICATION:
1. GET /properties/{id}/history returns snapshot array
2. Snapshots are ordered by date ascending
3. Response includes occupancy, noi, dscr fields
4. Swagger docs show the endpoint
5. ruff check . passes

When complete, output: PHASE4_COMPLETE
EOF

# =============================================================================
# EXECUTION
# =============================================================================

log "NLI-CMBS Historical Backfill"
log "Estimated runtime: 4-6 hours"
log "Log directory: $LOG_DIR"
echo ""

# Phase 1: Schema
log "═══════════════════════════════════════════════════════"
log "PHASE 1: Schema Migration (property_snapshots table)"
log "═══════════════════════════════════════════════════════"

if claude --dangerously-skip-permissions -p "$PHASE1_PROMPT" 2>&1 | tee "$LOG_DIR/phase1_schema_$TIMESTAMP.log"; then
    log "✓ Phase 1 complete"
else
    fail "Phase 1 failed. Check log."
fi

sleep 5

# Phase 2: Backfill Service
log "═══════════════════════════════════════════════════════"
log "PHASE 2: Backfill Service"
log "═══════════════════════════════════════════════════════"

if claude --dangerously-skip-permissions -p "$PHASE2_PROMPT" 2>&1 | tee "$LOG_DIR/phase2_backfill_$TIMESTAMP.log"; then
    log "✓ Phase 2 complete"
else
    fail "Phase 2 failed. Check log."
fi

sleep 5

# Phase 3: Validation
log "═══════════════════════════════════════════════════════"
log "PHASE 3: Validation Service"
log "═══════════════════════════════════════════════════════"

if claude --dangerously-skip-permissions -p "$PHASE3_PROMPT" 2>&1 | tee "$LOG_DIR/phase3_validation_$TIMESTAMP.log"; then
    log "✓ Phase 3 complete"
else
    fail "Phase 3 failed. Check log."
fi

sleep 5

# Phase 4: API Endpoint
log "═══════════════════════════════════════════════════════"
log "PHASE 4: API Endpoint for Property History"
log "═══════════════════════════════════════════════════════"

if claude --dangerously-skip-permissions -p "$PHASE4_PROMPT" 2>&1 | tee "$LOG_DIR/phase4_api_$TIMESTAMP.log"; then
    log "✓ Phase 4 complete"
else
    fail "Phase 4 failed. Check log."
fi

# =============================================================================
# RUN THE ACTUAL BACKFILL
# =============================================================================

log ""
log "═══════════════════════════════════════════════════════"
log "RUNNING BACKFILL (this will take 4-6 hours)"
log "═══════════════════════════════════════════════════════"

cd "$PROJECT_DIR"

# Activate venv and run backfill
source .venv/bin/activate 2>/dev/null || source venv/bin/activate 2>/dev/null || true

log "Starting backfill at $(date)"
python -m nli_cmbs.cli backfill --years 3 2>&1 | tee "$LOG_DIR/backfill_run_$TIMESTAMP.log"

log "Backfill completed at $(date)"

# =============================================================================
# VALIDATION
# =============================================================================

log ""
log "═══════════════════════════════════════════════════════"
log "VALIDATION: Spot-checking data against EDGAR"
log "═══════════════════════════════════════════════════════"

python -m nli_cmbs.cli validate --sample-size 20 2>&1 | tee "$LOG_DIR/validation_$TIMESTAMP.log"

# =============================================================================
# SUMMARY
# =============================================================================

log ""
log "═══════════════════════════════════════════════════════"
log "BACKFILL COMPLETE"
log "═══════════════════════════════════════════════════════"
log ""
log "Quick verification queries:"
log ""
log "  # Count snapshots per table"
log "  docker-compose exec postgres psql -U nli -d nli_cmbs -c \\"
log "    'SELECT (SELECT COUNT(*) FROM loan_snapshots) as loan_snaps,"
log "            (SELECT COUNT(*) FROM property_snapshots) as prop_snaps;'"
log ""
log "  # Check snapshot distribution per loan"
log "  docker-compose exec postgres psql -U nli -d nli_cmbs -c \\"
log "    'SELECT AVG(cnt), MIN(cnt), MAX(cnt) FROM ("
log "       SELECT COUNT(*) as cnt FROM loan_snapshots GROUP BY loan_id) x;'"
log ""
log "  # Test the API endpoint"
log "  curl http://localhost:8000/properties/{property_id}/history | jq '.snapshot_count'"
log ""
log "Logs saved to: $LOG_DIR"
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Deal(Base):
    __tablename__ = "deals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticker: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    trust_name: Mapped[str] = mapped_column(String(500), nullable=False)
    depositor_cik: Mapped[str] = mapped_column(String(20), nullable=False)
    trust_cik: Mapped[str | None] = mapped_column(String(20), nullable=True)
    issuer_shelf: Mapped[str] = mapped_column(String(50), nullable=False)
    issuance_year: Mapped[int] = mapped_column(Integer, nullable=False)
    original_balance: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True)
    loan_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    filings: Mapped[list["Filing"]] = relationship(back_populates="deal", cascade="all, delete-orphan")
    loans: Mapped[list["Loan"]] = relationship(back_populates="deal", cascade="all, delete-orphan")
    watchlist_items: Mapped[list["WatchlistItem"]] = relationship(back_populates="deal")
    reports: Mapped[list["Report"]] = relationship(back_populates="deal")


class Filing(Base):
    __tablename__ = "filings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("deals.id"), nullable=False)
    accession_number: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    filing_date: Mapped[date] = mapped_column(Date, nullable=False)
    reporting_period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    reporting_period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    form_type: Mapped[str] = mapped_column(String(20), nullable=False, default="ABS-EE")
    exhibit_url: Mapped[str] = mapped_column(Text, nullable=False)
    parsed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    deal: Mapped["Deal"] = relationship(back_populates="filings")
    snapshots: Mapped[list["LoanSnapshot"]] = relationship(back_populates="filing", cascade="all, delete-orphan")
    property_snapshots: Mapped[list["PropertySnapshot"]] = relationship(
        back_populates="filing", cascade="all, delete-orphan"
    )


class Loan(Base):
    __tablename__ = "loans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("deals.id"), nullable=False)
    prospectus_loan_id: Mapped[str] = mapped_column(String(100), nullable=False)
    asset_number: Mapped[int] = mapped_column(Integer, nullable=False)
    originator_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    original_loan_amount: Mapped[float] = mapped_column(Numeric(20, 2), nullable=False)
    origination_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    maturity_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    original_term_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    original_amortization_term_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    original_interest_rate: Mapped[float | None] = mapped_column(Numeric(8, 6), nullable=True)
    # Primary property info (for single-property loans or summary for multi-property)
    property_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    property_name: Mapped[str | None] = mapped_column(String(500), nullable=True, index=True)
    property_city: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    property_state: Mapped[str | None] = mapped_column(String(2), nullable=True, index=True)
    borrower_name: Mapped[str | None] = mapped_column(String(500), nullable=True, index=True)
    # Multi-property indicator
    property_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    interest_only_indicator: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    balloon_indicator: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    lien_position: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Modification tracking
    is_modified: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    modification_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    modification_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    modified_interest_rate: Mapped[float | None] = mapped_column(Numeric(7, 4), nullable=True)
    modified_maturity_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    modified_payment_amount: Mapped[float | None] = mapped_column(Numeric(16, 2), nullable=True)
    principal_forgiveness_amount: Mapped[float | None] = mapped_column(Numeric(16, 2), nullable=True)
    principal_deferral_amount: Mapped[float | None] = mapped_column(Numeric(16, 2), nullable=True)
    deferred_interest_amount: Mapped[float | None] = mapped_column(Numeric(16, 2), nullable=True)

    # AI-generated blurb for property modal
    ai_blurb: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_blurb_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    # Pari passu / A-B note linking: "1A", "1B" → parent "1"
    parent_loan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("loans.id", ondelete="SET NULL"), nullable=True
    )

    deal: Mapped["Deal"] = relationship(back_populates="loans")
    parent_loan: Mapped["Loan | None"] = relationship(
        back_populates="child_loans", remote_side="Loan.id"
    )
    child_loans: Mapped[list["Loan"]] = relationship(back_populates="parent_loan")
    snapshots: Mapped[list["LoanSnapshot"]] = relationship(back_populates="loan", cascade="all, delete-orphan")
    properties: Mapped[list["Property"]] = relationship(back_populates="loan", cascade="all, delete-orphan")
    watchlist_items: Mapped[list["WatchlistItem"]] = relationship(back_populates="loan")

    __table_args__ = (
        Index("uq_loans_deal_prospectus", "deal_id", "prospectus_loan_id", unique=True),
        Index("ix_loans_parent_loan_id", "parent_loan_id"),
    )


class Property(Base):
    """Individual property within a loan (for multi-property loans).
    
    For single-property loans, property info is stored directly on the Loan.
    For multi-property loans (property_count > 1), each property gets a row here.
    
    Property IDs follow the format "{loan_id}-{property_index}" e.g., "1-001", "1-002".
    """
    __tablename__ = "properties"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    loan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("loans.id", ondelete="CASCADE"), nullable=False)
    property_id: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., "1-001"
    
    # Property identification
    property_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    property_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    property_city: Mapped[str | None] = mapped_column(String(200), nullable=True)
    property_state: Mapped[str | None] = mapped_column(String(2), nullable=True)
    property_zip: Mapped[str | None] = mapped_column(String(20), nullable=True)
    property_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    property_type_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    property_type_source: Mapped[str | None] = mapped_column(String(20), nullable=True)  # 'reported' | 'inferred'
    
    # Physical characteristics
    net_rentable_sq_ft: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True)
    year_built: Mapped[int | None] = mapped_column(Integer, nullable=True)
    year_renovated: Mapped[int | None] = mapped_column(Integer, nullable=True)
    number_of_units: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Valuation
    valuation_securitization: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True)
    valuation_securitization_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    appraised_value: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True)
    appraisal_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    
    # Occupancy
    occupancy_securitization: Mapped[float | None] = mapped_column(Numeric(7, 4), nullable=True)
    occupancy_most_recent: Mapped[float | None] = mapped_column(Numeric(7, 4), nullable=True)
    
    # NOI / NCF
    noi_securitization: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True)
    noi_most_recent: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True)
    noi_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    ncf_securitization: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True)
    ncf_most_recent: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True)
    
    # DSCR
    dscr_noi_securitization: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    dscr_noi_most_recent: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    dscr_ncf_securitization: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    dscr_ncf_most_recent: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    
    # Financials
    revenue_most_recent: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True)
    operating_expenses_most_recent: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True)
    
    # Tenants
    largest_tenant: Mapped[str | None] = mapped_column(String(300), nullable=True)
    largest_tenant_sf: Mapped[int | None] = mapped_column(Integer, nullable=True)
    largest_tenant_lease_expiration: Mapped[date | None] = mapped_column(Date, nullable=True)
    largest_tenant_pct_nra: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)

    second_largest_tenant: Mapped[str | None] = mapped_column(String(300), nullable=True)
    second_largest_tenant_sf: Mapped[int | None] = mapped_column(Integer, nullable=True)
    second_largest_tenant_lease_expiration: Mapped[date | None] = mapped_column(Date, nullable=True)
    second_largest_tenant_pct_nra: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)

    third_largest_tenant: Mapped[str | None] = mapped_column(String(300), nullable=True)
    third_largest_tenant_sf: Mapped[int | None] = mapped_column(Integer, nullable=True)
    third_largest_tenant_lease_expiration: Mapped[date | None] = mapped_column(Date, nullable=True)
    third_largest_tenant_pct_nra: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    loan: Mapped["Loan"] = relationship(back_populates="properties")
    snapshots: Mapped[list["PropertySnapshot"]] = relationship(back_populates="property", order_by="PropertySnapshot.reporting_period_end")

    __table_args__ = (
        Index("ix_properties_loan_id", "loan_id"),
        Index("ix_properties_property_name", "property_name"),
        Index("ix_properties_property_city", "property_city"),
        Index("ix_properties_property_state", "property_state"),
        Index("uq_properties_loan_property_id", "loan_id", "property_id", unique=True),
    )


class PropertySnapshot(Base):
    """Time-series financial data for a property, one row per filing."""
    __tablename__ = "property_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"), nullable=False)
    filing_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("filings.id", ondelete="CASCADE"), nullable=False)
    reporting_period_end: Mapped[date] = mapped_column(Date, nullable=False)

    # Financials
    occupancy: Mapped[float | None] = mapped_column(Numeric(7, 4), nullable=True)
    noi: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True)
    ncf: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True)
    revenue: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True)
    operating_expenses: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True)
    dscr_noi: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    dscr_ncf: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)

    # Valuation
    valuation_amount: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True)
    valuation_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    valuation_source: Mapped[str | None] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=func.now())

    property: Mapped["Property"] = relationship(back_populates="snapshots")
    filing: Mapped["Filing"] = relationship(back_populates="property_snapshots")

    __table_args__ = (
        Index("uq_property_snapshots_property_filing", "property_id", "filing_id", unique=True),
    )


class LoanSnapshot(Base):
    __tablename__ = "loan_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    loan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("loans.id"), nullable=False)
    filing_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("filings.id"), nullable=False)
    reporting_period_begin_date: Mapped[date] = mapped_column(Date, nullable=False)
    reporting_period_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    beginning_balance: Mapped[float] = mapped_column(Numeric(20, 2), nullable=False)
    ending_balance: Mapped[float] = mapped_column(Numeric(20, 2), nullable=False)
    current_interest_rate: Mapped[float] = mapped_column(Numeric(8, 6), nullable=False)
    scheduled_interest_amount: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True)
    scheduled_principal_amount: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True)
    actual_interest_collected: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True)
    actual_principal_collected: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True)
    actual_other_collected: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True)
    servicer_advanced_amount: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True)
    delinquency_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    interest_paid_through_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    next_payment_amount_due: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True)
    # Current/most recent credit metrics (from BANK5-style filings with mostRecent* elements)
    dscr_noi: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    dscr_ncf: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    noi: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True)
    ncf: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True)
    occupancy: Mapped[float | None] = mapped_column(Numeric(7, 4), nullable=True)
    revenue: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True)
    operating_expenses: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True)
    debt_service: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True)
    appraised_value: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True)
    # Securitization-time credit metrics (from BMARK-style filings, fallback)
    dscr_noi_at_securitization: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    dscr_ncf_at_securitization: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    noi_at_securitization: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True)
    ncf_at_securitization: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True)
    occupancy_at_securitization: Mapped[float | None] = mapped_column(Numeric(7, 4), nullable=True)
    appraised_value_at_securitization: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    loan: Mapped["Loan"] = relationship(back_populates="snapshots")
    filing: Mapped["Filing"] = relationship(back_populates="snapshots")

    __table_args__ = (
        Index("uq_snapshots_loan_filing", "loan_id", "filing_id", unique=True),
    )


class CikMapping(Base):
    __tablename__ = "cik_mappings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deal_ticker: Mapped[str] = mapped_column(String(100), nullable=False)
    issuer_shelf: Mapped[str] = mapped_column(String(50), nullable=False)
    trust_name: Mapped[str] = mapped_column(String(500), nullable=False)
    depositor_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    depositor_cik: Mapped[str] = mapped_column(String(20), nullable=False)
    trust_cik: Mapped[str | None] = mapped_column(String(20), nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    @property
    def effective_cik(self) -> str:
        """Return trust CIK if available, otherwise depositor CIK.

        Trust CIK is unique per deal and preferred for filing lookups.
        Depositor CIK is shared across deals from the same shelf.
        """
        return self.trust_cik or self.depositor_cik

    __table_args__ = (
        Index("ix_cik_mappings_deal_ticker", "deal_ticker"),
        Index("ix_cik_mappings_issuer_shelf", "issuer_shelf"),
        Index("ix_cik_mappings_depositor_cik", "depositor_cik"),
    )


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    loan_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("loans.id"), nullable=True)
    deal_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("deals.id"), nullable=True)
    label: Mapped[str | None] = mapped_column(String(500), nullable=True)
    alert_on_delinquency_change: Mapped[bool] = mapped_column(Boolean, default=True)
    alert_on_servicer_advance: Mapped[bool] = mapped_column(Boolean, default=False)
    alert_on_maturity_within_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_checked_filing_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("filings.id"), nullable=True
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    loan: Mapped["Loan | None"] = relationship(back_populates="watchlist_items")
    deal: Mapped["Deal | None"] = relationship(back_populates="watchlist_items")
    last_checked_filing: Mapped["Filing | None"] = relationship(foreign_keys=[last_checked_filing_id])


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("deals.id"), nullable=False)
    filing_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("filings.id"), nullable=False)
    report_type: Mapped[str] = mapped_column(String(50), default="surveillance")
    report_text: Mapped[str] = mapped_column(Text, nullable=False)
    model_used: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    deal: Mapped["Deal"] = relationship(back_populates="reports")
    filing: Mapped["Filing"] = relationship()


class GroundTruthEntry(Base):
    """Flat field-level ground truth records for evaluation scoring.

    Each row = one verifiable fact from an ABS-EE filing.
    Shape: (deal, loan, field_name, value, filing) — the answer key.
    """
    __tablename__ = "ground_truth_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("deals.id"), nullable=False)
    loan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("loans.id"), nullable=False)
    filing_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("filings.id"), nullable=False)

    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    field_value: Mapped[str] = mapped_column(Text, nullable=False)
    field_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "numeric", "date", "text", "boolean"

    tier: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    created_at: Mapped[datetime] = mapped_column(default=func.now())

    __table_args__ = (
        Index("ix_gt_deal_loan_field", "deal_id", "loan_id", "field_name"),
        Index("ix_gt_filing", "filing_id"),
        Index("ix_gt_tier", "tier"),
    )


class InferenceLog(Base):
    """Raw log of every AI inference call for evaluation and debugging."""
    __tablename__ = "inference_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    task_type: Mapped[str] = mapped_column(String(50), nullable=False)
    deal_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("deals.id"), nullable=True)
    loan_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("loans.id"), nullable=True)
    filing_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("filings.id"), nullable=True)

    model_id: Mapped[str] = mapped_column(String(100), nullable=False)

    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    user_prompt: Mapped[str] = mapped_column(Text, nullable=False)

    raw_response: Mapped[str] = mapped_column(Text, nullable=False)

    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)

    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=func.now())

    __table_args__ = (
        Index("ix_inference_logs_model", "model_id"),
        Index("ix_inference_logs_task", "task_type"),
        Index("ix_inference_logs_deal", "deal_id"),
        Index("ix_inference_logs_created", "created_at"),
    )


class ResearchReport(Base):
    """PDF research reports ingested into the knowledge base."""
    __tablename__ = "research_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename: Mapped[str] = mapped_column(String(500), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(1000), nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="Trepp")
    published_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    full_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_themes: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())


class MarketArticle(Base):
    """CMBS market news articles ingested from RSS feeds (Trepp, CREFC, etc.)."""
    __tablename__ = "market_articles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    url: Mapped[str] = mapped_column(String(2000), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(1000), nullable=False)
    author: Mapped[str | None] = mapped_column(String(300), nullable=True)
    published_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="Trepp")

    # AI-generated fields
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_themes: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    __table_args__ = (
        Index("ix_market_articles_source", "source"),
    )

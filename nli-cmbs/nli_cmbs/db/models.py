import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, ForeignKey, Index, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
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
    property_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    property_name: Mapped[str | None] = mapped_column(String(500), nullable=True, index=True)
    property_city: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    property_state: Mapped[str | None] = mapped_column(String(2), nullable=True, index=True)
    borrower_name: Mapped[str | None] = mapped_column(String(500), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    deal: Mapped["Deal"] = relationship(back_populates="loans")
    snapshots: Mapped[list["LoanSnapshot"]] = relationship(back_populates="loan", cascade="all, delete-orphan")
    watchlist_items: Mapped[list["WatchlistItem"]] = relationship(back_populates="loan")


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
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    loan: Mapped["Loan"] = relationship(back_populates="snapshots")
    filing: Mapped["Filing"] = relationship(back_populates="snapshots")


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

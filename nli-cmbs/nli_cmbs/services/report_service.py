"""Surveillance report generation with caching."""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from nli_cmbs.ai.client import AnthropicClient
from nli_cmbs.ai.exceptions import AIGenerationError
from nli_cmbs.ai.prompts import (
    SURVEILLANCE_SYSTEM_PROMPT,
    build_surveillance_prompt,
    format_delinquency_status,
)
from nli_cmbs.db.models import Filing, Loan, LoanSnapshot, Report
from nli_cmbs.schemas.report import ReportResponse
from nli_cmbs.services.deal_service import DealService
from nli_cmbs.services.metrics import compute_deal_metrics

logger = logging.getLogger(__name__)


class DealNotFoundError(Exception):
    pass


class ReportService:
    def __init__(
        self,
        db: AsyncSession,
        ai_client: AnthropicClient,
        deal_service: DealService,
    ) -> None:
        self._db = db
        self._ai = ai_client
        self._deal_service = deal_service

    async def generate_surveillance_report(
        self, ticker: str, regenerate: bool = False
    ) -> ReportResponse:
        # 1. Fetch deal
        deal = await self._deal_service.get_by_ticker(ticker)
        if not deal:
            raise DealNotFoundError(f"Deal {ticker} not found")

        # 2. Get latest parsed filing
        filing_stmt = (
            select(Filing)
            .where(Filing.deal_id == deal.id, Filing.parsed.is_(True))
            .order_by(Filing.filing_date.desc())
            .limit(1)
        )
        filing = (await self._db.execute(filing_stmt)).scalar_one_or_none()
        if not filing:
            raise AIGenerationError(f"No parsed filing found for {ticker}")

        # 3. Check cache
        if not regenerate:
            cached_report = await self._get_cached_report(deal.id, filing.id)
            if cached_report:
                return ReportResponse(
                    deal_ticker=ticker,
                    report_text=cached_report.report_text,
                    generated_at=cached_report.generated_at,
                    model_used=cached_report.model_used,
                    filing_date=str(filing.filing_date),
                    accession_number=filing.accession_number,
                    cached=True,
                )

        # 4. Fetch deal summary via metrics
        metrics = await compute_deal_metrics(self._db, deal.id)
        deal_summary = {
            "deal_name": deal.ticker,
            "current_upb": metrics.total_upb,
            "original_upb": float(deal.original_balance) if deal.original_balance else 0,
            "loan_count": metrics.loan_count,
            "wa_coupon": round(metrics.wa_coupon, 2) if metrics.wa_coupon else "N/A",
            "wa_dscr": round(metrics.wa_dscr, 2) if metrics.wa_dscr else "N/A",
            "wa_ltv": round(metrics.wa_ltv, 1) if metrics.wa_ltv else "N/A",
            "wa_occupancy": round(metrics.wa_occupancy, 1) if metrics.wa_occupancy else "N/A",
        }

        # 5. Fetch top 10 loans by balance
        top_loans = await self._get_top_loans(deal.id, filing.id, limit=10)

        # 6. Fetch delinquent loans (status != Current / "0")
        delinquent_loans = await self._get_delinquent_loans(deal.id, filing.id)

        # 7. Fetch specially serviced loans (status "2" or "3" — Foreclosure/REO)
        specially_serviced = await self._get_specially_serviced_loans(deal.id, filing.id)

        # 8. Fetch maturity schedule
        maturity_schedule = await self._get_maturity_schedule(deal.id)

        # 9. Filing metadata
        filing_metadata = {
            "filing_date": str(filing.filing_date),
            "accession_number": filing.accession_number,
            "edgar_url": filing.exhibit_url,
        }

        # 10. Preprocess delinquency codes (already handled in prompt builder)

        # 11. Build prompt
        user_prompt = build_surveillance_prompt(
            deal_summary=deal_summary,
            top_loans=top_loans,
            delinquent_loans=delinquent_loans,
            specially_serviced_loans=specially_serviced,
            maturity_schedule=maturity_schedule,
            filing_metadata=filing_metadata,
        )

        # 12. Call AI
        logger.info("Generating surveillance report for %s", ticker)
        report_text = await self._ai.generate_report(
            system_prompt=SURVEILLANCE_SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )

        # 13. Cache the report
        report = Report(
            deal_id=deal.id,
            filing_id=filing.id,
            report_type="surveillance",
            report_text=report_text,
            model_used=self._ai._model,
            prompt_tokens=self._ai.count_tokens(user_prompt),
            completion_tokens=self._ai.count_tokens(report_text),
        )
        self._db.add(report)
        await self._db.commit()
        await self._db.refresh(report)

        return ReportResponse(
            deal_ticker=ticker,
            report_text=report_text,
            generated_at=report.generated_at or datetime.utcnow(),
            model_used=self._ai._model,
            filing_date=str(filing.filing_date),
            accession_number=filing.accession_number,
            cached=False,
        )

    async def _get_cached_report(self, deal_id, filing_id) -> Report | None:
        stmt = (
            select(Report)
            .where(
                Report.deal_id == deal_id,
                Report.filing_id == filing_id,
                Report.report_type == "surveillance",
            )
            .order_by(Report.generated_at.desc())
            .limit(1)
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def _get_top_loans(self, deal_id, filing_id, limit: int = 10) -> list[dict]:
        stmt = (
            select(
                Loan.prospectus_loan_id,
                Loan.property_name,
                Loan.property_type,
                Loan.property_city,
                Loan.property_state,
                Loan.maturity_date,
                LoanSnapshot.ending_balance,
                LoanSnapshot.dscr_noi,
                LoanSnapshot.occupancy,
            )
            .join(LoanSnapshot, LoanSnapshot.loan_id == Loan.id)
            .where(Loan.deal_id == deal_id, LoanSnapshot.filing_id == filing_id)
            .order_by(LoanSnapshot.ending_balance.desc())
            .limit(limit)
        )
        rows = (await self._db.execute(stmt)).all()
        return [
            {
                "prospectus_loan_id": row.prospectus_loan_id or "N/A",
                "property_name": row.property_name or "N/A",
                "property_type": row.property_type or "N/A",
                "city": row.property_city or "N/A",
                "state": row.property_state or "N/A",
                "current_upb": float(row.ending_balance or 0),
                "dscr": round(float(row.dscr_noi), 2) if row.dscr_noi else "N/A",
                "occupancy": round(float(row.occupancy) * 100, 1) if row.occupancy else "N/A",
                "maturity_date": str(row.maturity_date) if row.maturity_date else "N/A",
            }
            for row in rows
        ]

    async def _get_delinquent_loans(self, deal_id, filing_id) -> list[dict]:
        stmt = (
            select(
                Loan.prospectus_loan_id,
                Loan.property_name,
                Loan.property_type,
                Loan.property_city,
                Loan.property_state,
                LoanSnapshot.ending_balance,
                LoanSnapshot.delinquency_status,
            )
            .join(LoanSnapshot, LoanSnapshot.loan_id == Loan.id)
            .where(
                Loan.deal_id == deal_id,
                LoanSnapshot.filing_id == filing_id,
                LoanSnapshot.delinquency_status.isnot(None),
                LoanSnapshot.delinquency_status != "0",
                LoanSnapshot.delinquency_status != "",
            )
            .order_by(LoanSnapshot.ending_balance.desc())
        )
        rows = (await self._db.execute(stmt)).all()
        return [
            {
                "prospectus_loan_id": row.prospectus_loan_id or "N/A",
                "property_name": row.property_name or "N/A",
                "property_type": row.property_type or "N/A",
                "city": row.property_city or "N/A",
                "state": row.property_state or "N/A",
                "current_upb": float(row.ending_balance or 0),
                "delinquency_code": row.delinquency_status,
                "status": format_delinquency_status(row.delinquency_status or ""),
            }
            for row in rows
        ]

    async def _get_specially_serviced_loans(self, deal_id, filing_id) -> list[dict]:
        stmt = (
            select(
                Loan.prospectus_loan_id,
                Loan.property_name,
                Loan.property_type,
                Loan.property_city,
                Loan.property_state,
                LoanSnapshot.ending_balance,
            )
            .join(LoanSnapshot, LoanSnapshot.loan_id == Loan.id)
            .where(
                Loan.deal_id == deal_id,
                LoanSnapshot.filing_id == filing_id,
                LoanSnapshot.delinquency_status.in_(["2", "3"]),
            )
            .order_by(LoanSnapshot.ending_balance.desc())
        )
        rows = (await self._db.execute(stmt)).all()
        return [
            {
                "prospectus_loan_id": row.prospectus_loan_id or "N/A",
                "property_name": row.property_name or "N/A",
                "property_type": row.property_type or "N/A",
                "city": row.property_city or "N/A",
                "state": row.property_state or "N/A",
                "current_upb": float(row.ending_balance or 0),
            }
            for row in rows
        ]

    async def _get_maturity_schedule(self, deal_id) -> list[dict]:
        stmt = (
            select(
                extract("year", Loan.maturity_date).label("year"),
                func.count().label("loan_count"),
                func.sum(Loan.original_loan_amount).label("total_balance"),
            )
            .where(Loan.deal_id == deal_id, Loan.maturity_date.isnot(None))
            .group_by(extract("year", Loan.maturity_date))
            .order_by(extract("year", Loan.maturity_date))
        )
        rows = (await self._db.execute(stmt)).all()
        return [
            {
                "year": int(row.year),
                "loan_count": row.loan_count,
                "total_balance": float(row.total_balance),
            }
            for row in rows
        ]

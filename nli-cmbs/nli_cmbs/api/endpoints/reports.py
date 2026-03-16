import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from nli_cmbs.ai.client import AnthropicClient, get_anthropic_client
from nli_cmbs.ai.exceptions import AIGenerationError
from nli_cmbs.db.session import get_session
from nli_cmbs.schemas.report import ReportResponse
from nli_cmbs.services.deal_service import DealService
from nli_cmbs.services.report_service import DealNotFoundError, ReportService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/{ticker}/report", response_model=ReportResponse)
async def get_deal_report(
    ticker: str,
    regenerate: bool = False,
    session: AsyncSession = Depends(get_session),
    ai_client: AnthropicClient = Depends(get_anthropic_client),
):
    """Generate or retrieve a surveillance report for a CMBS deal."""
    service = ReportService(session, ai_client, DealService(session))
    try:
        return await service.generate_surveillance_report(ticker, regenerate)
    except DealNotFoundError:
        raise HTTPException(status_code=404, detail=f"Deal {ticker} not found")
    except AIGenerationError as e:
        raise HTTPException(status_code=500, detail=f"Report generation failed: {e}")
    except Exception as e:
        logger.exception("Unexpected error generating report for %s", ticker)
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")

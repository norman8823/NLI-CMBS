from fastapi import APIRouter

from nli_cmbs.api.endpoints import deals, health, loans, market, properties, reports

router = APIRouter()
router.include_router(health.router, tags=["health"])
router.include_router(deals.router, prefix="/deals", tags=["deals"])
router.include_router(loans.router, prefix="/loans", tags=["loans"])
router.include_router(loans.router, prefix="/deals", tags=["deals"])
router.include_router(properties.router, prefix="/properties", tags=["properties"])
router.include_router(reports.router, prefix="/deals", tags=["reports"])
router.include_router(market.router, prefix="/market", tags=["market"])

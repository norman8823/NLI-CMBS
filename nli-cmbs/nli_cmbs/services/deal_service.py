from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nli_cmbs.db.models import Deal


class DealService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_ticker(self, ticker: str) -> Deal | None:
        result = await self._session.execute(select(Deal).where(Deal.ticker == ticker))
        return result.scalar_one_or_none()

    async def create(self, **kwargs) -> Deal:
        deal = Deal(**kwargs)
        self._session.add(deal)
        await self._session.commit()
        await self._session.refresh(deal)
        return deal

    async def list_all(self) -> list[Deal]:
        result = await self._session.execute(select(Deal).order_by(Deal.created_at.desc()))
        return list(result.scalars().all())

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from nli_cmbs.config import settings

engine: AsyncEngine = create_async_engine(settings.DATABASE_URL, echo=False)

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class MarketArticleOut(BaseModel):
    id: UUID
    url: str
    title: str
    author: str | None = None
    published_date: datetime
    excerpt: str | None = None
    source: str
    summary: str | None = None
    key_themes: list[str] | None = None
    ingested_at: datetime

    model_config = {"from_attributes": True}


class ThemeCount(BaseModel):
    theme: str
    count: int


class ThemesOut(BaseModel):
    themes: list[ThemeCount]
    article_count: int
    days: int

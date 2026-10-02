from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ArticleBase(BaseModel):
    title: str
    source: Optional[str] = None
    url: str
    content: Optional[str] = None
    published_at: Optional[datetime] = None


class ArticleCreate(ArticleBase):
    pass


class ArticleResponse(ArticleBase):
    id: int
    sentiment_label: Optional[str] = None
    sentiment_score: Optional[float] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FetchRequest(BaseModel):
    query: str
    page_size: int = 20


class AnalyticsResponse(BaseModel):
    total_articles: int
    positive_count: int
    negative_count: int
    neutral_count: int
    average_sentiment_score: float


class DailyTrendResponse(BaseModel):
    date: str
    article_count: int
    average_sentiment: float
    average_sentiment_score: Optional[float] = None
    positive_count: Optional[int] = 0
    negative_count: Optional[int] = 0
    neutral_count: Optional[int] = 0
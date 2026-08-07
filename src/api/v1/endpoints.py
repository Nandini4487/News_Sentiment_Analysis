from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.models.article_model import Article
from src.schemas.article_schema import ArticleResponse, FetchRequest, AnalyticsResponse
from src.services.news_service import news_service, NewsServiceError
from src.services.ml_service import ml_service

router = APIRouter()


@router.post("/fetch", response_model=List[ArticleResponse], status_code=201)
def fetch_and_analyze(payload: FetchRequest, db: Session = Depends(get_db)):
    try:
        raw_articles = news_service.fetch_articles(payload.query, payload.page_size)
    except NewsServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    saved_articles = []
    for item in raw_articles:
        if not item["url"]:
            continue
        if db.query(Article).filter(Article.url == item["url"]).first():
            continue

        label, score = ml_service.analyze(item["content"] or item["title"])

        article = Article(
            title=item["title"],
            source=item["source"],
            url=item["url"],
            content=item["content"],
            published_at=item["published_at"],
            sentiment_label=label,
            sentiment_score=score,
        )
        db.add(article)
        saved_articles.append(article)

    db.commit()
    for article in saved_articles:
        db.refresh(article)

    return saved_articles


@router.get("/articles", response_model=List[ArticleResponse])
def list_articles(skip: int = 0, limit: int = 50, sentiment: str | None = None, db: Session = Depends(get_db)):
    query = db.query(Article)
    if sentiment:
        query = query.filter(Article.sentiment_label == sentiment)
    return query.order_by(Article.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/analytics", response_model=AnalyticsResponse)
def get_analytics(db: Session = Depends(get_db)):
    total = db.query(Article).count()
    if total == 0:
        return AnalyticsResponse(
            total_articles=0, positive_count=0, negative_count=0,
            neutral_count=0, average_sentiment_score=0.0,
        )

    positive = db.query(Article).filter(Article.sentiment_label == "positive").count()
    negative = db.query(Article).filter(Article.sentiment_label == "negative").count()
    neutral = db.query(Article).filter(Article.sentiment_label == "neutral").count()
    avg_score = db.query(func.avg(Article.sentiment_score)).scalar() or 0.0

    return AnalyticsResponse(
        total_articles=total, positive_count=positive, negative_count=negative,
        neutral_count=neutral, average_sentiment_score=round(avg_score, 4),
    )
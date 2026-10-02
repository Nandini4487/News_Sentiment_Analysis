from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.models.article_model import Article
from src.schemas.article_schema import ArticleResponse, FetchRequest, AnalyticsResponse, DailyTrendResponse
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
    seen_urls = set()
    for item in raw_articles:
        url = item.get("url")
        if not url or url in seen_urls:
            continue
        if db.query(Article).filter(Article.url == url).first():
            continue

        seen_urls.add(url)
        label, score = ml_service.analyze(item.get("content") or item.get("title") or "")

        article = Article(
            title=item.get("title") or "Untitled",
            source=item.get("source"),
            url=url,
            content=item.get("content"),
            published_at=item.get("published_at"),
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


@router.get("/analytics/trend", response_model=List[DailyTrendResponse])
def get_sentiment_trend(
    query: Optional[str] = None,
    days: int = Query(7, ge=1, description="Number of past days to analyze"),
    db: Session = Depends(get_db),
):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).replace(tzinfo=None)
    db_query = db.query(Article).filter(
        func.coalesce(Article.published_at, Article.created_at) >= cutoff
    )

    if query and query.strip():
        search_pattern = f"%{query.strip()}%"
        db_query = db_query.filter(
            or_(
                Article.title.ilike(search_pattern),
                Article.content.ilike(search_pattern),
            )
        )

    articles = db_query.all()

    daily_groups = defaultdict(list)
    for article in articles:
        dt = article.published_at or article.created_at
        if dt:
            if dt.tzinfo is not None:
                date_str = dt.astimezone(timezone.utc).strftime("%Y-%m-%d")
            else:
                date_str = dt.strftime("%Y-%m-%d")
            daily_groups[date_str].append(article)

    trend_list = []
    for date_str in sorted(daily_groups.keys()):
        group = daily_groups[date_str]
        scores = [a.sentiment_score for a in group if a.sentiment_score is not None]
        avg_score = round(sum(scores) / len(scores), 4) if scores else 0.0
        pos_count = sum(1 for a in group if a.sentiment_label == "positive")
        neg_count = sum(1 for a in group if a.sentiment_label == "negative")
        neu_count = sum(1 for a in group if a.sentiment_label == "neutral")

        trend_list.append(
            DailyTrendResponse(
                date=date_str,
                article_count=len(group),
                average_sentiment=avg_score,
                average_sentiment_score=avg_score,
                positive_count=pos_count,
                negative_count=neg_count,
                neutral_count=neu_count,
            )
        )

    return trend_list
from datetime import datetime, timezone
from unittest.mock import patch

from src.core.database import SessionLocal
from src.models.article_model import Article
from src.services.scheduler_service import fetch_and_store_topics, start_scheduler, stop_scheduler, scheduler
from src.services.news_service import NewsServiceError


def test_scheduler_fetch_and_store_duplicates():
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    mock_articles = [
        {
            "title": "Exciting AI breakthrough and innovations",
            "source": "TechDaily",
            "url": "https://example.com/scheduler_test_dup_1",
            "content": "This is great, fantastic and wonderful news.",
            "published_at": now,
        },
        {
            "title": "Exciting AI breakthrough duplicate in batch",
            "source": "TechDaily",
            "url": "https://example.com/scheduler_test_dup_1",  # duplicate URL in same batch
            "content": "Duplicate content",
            "published_at": now,
        },
        {
            "title": "Disastrous stock market drop",
            "source": "FinanceNow",
            "url": "https://example.com/scheduler_test_dup_2",
            "content": "Terrible decline and disastrous drop in stocks.",
            "published_at": now,
        },
    ]

    db = SessionLocal()
    # Clean up any previous test articles if present
    db.query(Article).filter(
        Article.url.in_([
            "https://example.com/scheduler_test_dup_1",
            "https://example.com/scheduler_test_dup_2"
        ])
    ).delete(synchronize_session=False)
    db.commit()

    try:
        with patch("src.services.scheduler_service.news_service.fetch_articles", return_value=mock_articles):
            # First run: should save 2 articles (duplicate in batch skipped)
            saved_count = fetch_and_store_topics(topics=["tech"], db=db)
            assert saved_count == 2

            # Check they were properly scored and stored
            a1 = db.query(Article).filter(Article.url == "https://example.com/scheduler_test_dup_1").first()
            assert a1 is not None
            assert a1.sentiment_label == "positive"
            assert a1.sentiment_score > 0

            a2 = db.query(Article).filter(Article.url == "https://example.com/scheduler_test_dup_2").first()
            assert a2 is not None
            assert a2.sentiment_label == "negative"
            assert a2.sentiment_score < 0

            # Second run with same URLs: should skip existing duplicates and save 0 new articles
            saved_count_2 = fetch_and_store_topics(topics=["tech"], db=db)
            assert saved_count_2 == 0
    finally:
        db.query(Article).filter(
            Article.url.in_([
                "https://example.com/scheduler_test_dup_1",
                "https://example.com/scheduler_test_dup_2"
            ])
        ).delete(synchronize_session=False)
        db.commit()
        db.close()


def test_scheduler_handles_news_service_error():
    db = SessionLocal()
    try:
        with patch("src.services.scheduler_service.news_service.fetch_articles", side_effect=NewsServiceError("API Limit reached")):
            # Should not raise exception and return 0 saved
            saved_count = fetch_and_store_topics(topics=["fail_topic"], db=db)
            assert saved_count == 0
    finally:
        db.close()


def test_scheduler_start_and_stop():
    stop_scheduler()
    assert not scheduler.running

    start_scheduler()
    assert scheduler.running

    # Starting again should be idempotent
    start_scheduler()
    assert scheduler.running

    stop_scheduler()
    assert not scheduler.running

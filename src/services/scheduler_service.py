import logging
from typing import List, Optional
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from src.core.config import settings
from src.core.database import SessionLocal
from src.models.article_model import Article
from src.services.ml_service import ml_service
from src.services.news_service import news_service, NewsServiceError

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def fetch_and_store_topics(topics: Optional[List[str]] = None, db: Optional[Session] = None) -> int:
    """
    Fetch news for the specified topics (or settings.SCHEDULER_TOPICS),
    score sentiment with VADER, and save to the database skipping duplicates.
    Returns total number of newly saved articles.
    """
    target_topics = topics if topics is not None else settings.SCHEDULER_TOPICS
    should_close_db = False
    if db is None:
        db = SessionLocal()
        should_close_db = True

    total_saved = 0
    try:
        for topic in target_topics:
            logger.info(f"Scheduler: Fetching articles for topic '{topic}'")
            try:
                raw_articles = news_service.fetch_articles(topic)
            except NewsServiceError as exc:
                logger.error(f"Scheduler: NewsServiceError for topic '{topic}': {exc}")
                continue
            except Exception as exc:
                logger.error(f"Scheduler: Unexpected error fetching topic '{topic}': {exc}")
                continue

            new_articles = []
            for item in raw_articles:
                url = item.get("url")
                if not url:
                    continue

                # Skip duplicates existing in DB
                if db.query(Article).filter(Article.url == url).first():
                    continue

                # Skip duplicates within the same batch
                if any(a.url == url for a in new_articles):
                    continue

                text_to_analyze = item.get("content") or item.get("title") or ""
                label, score = ml_service.analyze(text_to_analyze)

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
                new_articles.append(article)

            if new_articles:
                db.commit()
                total_saved += len(new_articles)
                logger.info(f"Scheduler: Saved {len(new_articles)} new articles for topic '{topic}'")
            else:
                logger.info(f"Scheduler: No new articles to save for topic '{topic}'")

    except Exception as exc:
        db.rollback()
        logger.error(f"Scheduler: Error during topic processing: {exc}")
    finally:
        if should_close_db:
            db.close()

    return total_saved


def start_scheduler() -> None:
    """Start the APScheduler background scheduler if enabled and not already running."""
    if not settings.SCHEDULER_ENABLED:
        logger.info("Scheduler: Disabled by configuration (SCHEDULER_ENABLED=False)")
        return

    if not scheduler.running:
        scheduler.add_job(
            fetch_and_store_topics,
            "interval",
            hours=settings.SCHEDULER_INTERVAL_HOURS,
            id="scheduled_news_fetch",
            replace_existing=True,
        )
        scheduler.start()
        logger.info(
            f"Scheduler: Started APScheduler with interval {settings.SCHEDULER_INTERVAL_HOURS} hour(s) for topics: {settings.SCHEDULER_TOPICS}"
        )


def stop_scheduler() -> None:
    """Stop the APScheduler background scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler: APScheduler shut down successfully")

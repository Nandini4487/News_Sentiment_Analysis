from datetime import datetime, timezone
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.main import app
from src.core.database import Base, get_db
from src.models.article_model import Article
from src.services.news_service import NewsServiceError

# In-memory SQLite database for isolated unit testing
TEST_DATABASE_URL = "sqlite:///:memory:"
engine_test = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_and_teardown_db():
    Base.metadata.create_all(bind=engine_test)
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=engine_test)


def test_health_check():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_list_articles_empty_ok():
    response = client.get("/api/v1/articles")
    assert response.status_code == 200
    assert response.json() == []


def test_fetch_requires_query_field():
    response = client.post("/api/v1/fetch", json={})
    assert response.status_code == 422


def test_fetch_saves_articles_with_sentiment_and_skips_duplicates():
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    mock_articles = [
        {
            "title": "Amazing Breakthrough in Tech",
            "source": "TechDaily",
            "url": "https://example.com/art1",
            "content": "This is wonderful, awesome, fantastic and brilliant news!",
            "published_at": now,
        },
        {
            "title": "Terrible Economic Collapse",
            "source": "MarketWatch",
            "url": "https://example.com/art2",
            "content": "A disastrous catastrophe and terrible crisis has occurred.",
            "published_at": now,
        },
        {
            "title": "Amazing Breakthrough in Tech (Duplicate URL in payload)",
            "source": "TechDaily",
            "url": "https://example.com/art1",
            "content": "Duplicate content",
            "published_at": now,
        },
    ]

    with patch("src.api.v1.endpoints.news_service.fetch_articles", return_value=mock_articles):
        # 1. First fetch: should save 2 unique articles and compute VADER sentiment
        response = client.post("/api/v1/fetch", json={"query": "tech", "page_size": 10})
        assert response.status_code == 201
        data = response.json()
        assert len(data) == 2

        # Check sentiment label & score
        art1 = next(a for a in data if a["url"] == "https://example.com/art1")
        assert art1["sentiment_label"] == "positive"
        assert art1["sentiment_score"] > 0

        art2 = next(a for a in data if a["url"] == "https://example.com/art2")
        assert art2["sentiment_label"] == "negative"
        assert art2["sentiment_score"] < 0

        # 2. Second fetch with identical data: duplicate URLs must be skipped
        response_dup = client.post("/api/v1/fetch", json={"query": "tech", "page_size": 10})
        assert response_dup.status_code == 201
        assert response_dup.json() == []


def test_fetch_news_service_error_returns_clean_502():
    with patch(
        "src.api.v1.endpoints.news_service.fetch_articles",
        side_effect=NewsServiceError("NewsAPI rate limit reached (429)"),
    ):
        response = client.post("/api/v1/fetch", json={"query": "crypto"})
        assert response.status_code == 502
        assert response.json()["detail"] == "NewsAPI rate limit reached (429)"


def test_list_articles_sentiment_filter():
    db = TestingSessionLocal()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    a1 = Article(
        title="Positive News",
        url="https://example.com/pos",
        published_at=now,
        sentiment_label="positive",
        sentiment_score=0.7,
    )
    a2 = Article(
        title="Negative News",
        url="https://example.com/neg",
        published_at=now,
        sentiment_label="negative",
        sentiment_score=-0.5,
    )
    a3 = Article(
        title="Neutral News",
        url="https://example.com/neu",
        published_at=now,
        sentiment_label="neutral",
        sentiment_score=0.0,
    )
    db.add_all([a1, a2, a3])
    db.commit()
    db.close()

    # Filter positive
    r_pos = client.get("/api/v1/articles?sentiment=positive")
    assert r_pos.status_code == 200
    pos_data = r_pos.json()
    assert len(pos_data) == 1
    assert pos_data[0]["url"] == "https://example.com/pos"

    # Filter negative
    r_neg = client.get("/api/v1/articles?sentiment=negative")
    assert r_neg.status_code == 200
    neg_data = r_neg.json()
    assert len(neg_data) == 1
    assert neg_data[0]["url"] == "https://example.com/neg"

    # Filter neutral
    r_neu = client.get("/api/v1/articles?sentiment=neutral")
    assert r_neu.status_code == 200
    neu_data = r_neu.json()
    assert len(neu_data) == 1
    assert neu_data[0]["url"] == "https://example.com/neu"

    # No filter: returns all 3
    r_all = client.get("/api/v1/articles")
    assert r_all.status_code == 200
    assert len(r_all.json()) == 3


def test_analytics_with_known_test_data():
    db = TestingSessionLocal()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # 2 positive (0.8, 0.4), 1 negative (-0.6), 1 neutral (0.0)
    # Average = (0.8 + 0.4 - 0.6 + 0.0) / 4 = 0.6 / 4 = 0.15
    articles = [
        Article(title="P1", url="https://example.com/p1", published_at=now, sentiment_label="positive", sentiment_score=0.8),
        Article(title="P2", url="https://example.com/p2", published_at=now, sentiment_label="positive", sentiment_score=0.4),
        Article(title="N1", url="https://example.com/n1", published_at=now, sentiment_label="negative", sentiment_score=-0.6),
        Article(title="Neu1", url="https://example.com/neu1", published_at=now, sentiment_label="neutral", sentiment_score=0.0),
    ]
    db.add_all(articles)
    db.commit()
    db.close()

    response = client.get("/api/v1/analytics")
    assert response.status_code == 200
    data = response.json()

    assert data["total_articles"] == 4
    assert data["positive_count"] == 2
    assert data["negative_count"] == 1
    assert data["neutral_count"] == 1
    assert data["average_sentiment_score"] == 0.15


def test_analytics_empty_database():
    response = client.get("/api/v1/analytics")
    assert response.status_code == 200
    data = response.json()

    assert data["total_articles"] == 0
    assert data["positive_count"] == 0
    assert data["negative_count"] == 0
    assert data["neutral_count"] == 0
    assert data["average_sentiment_score"] == 0.0
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from src.main import app
from src.core.database import SessionLocal
from src.models.article_model import Article

client = TestClient(app)


def test_trend_endpoint_empty_or_valid():
    response = client.get("/api/v1/analytics/trend?days=7")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_trend_endpoint_with_data():
    db = SessionLocal()
    now = datetime.now(timezone.utc)
    
    unique_tag = f"trend_test_{int(now.timestamp())}"
    # Insert two test articles for "today"
    a1 = Article(
        title=f"Great AI breakthrough in research {unique_tag}",
        source="Tech Journal",
        url=f"https://example.com/{unique_tag}_1",
        content="Artificial intelligence is performing wonderfully and making amazing progress.",
        published_at=now.replace(tzinfo=None),
        sentiment_label="positive",
        sentiment_score=0.8,
    )
    a2 = Article(
        title=f"Severe AI system failure and crisis {unique_tag}",
        source="Tech Journal",
        url=f"https://example.com/{unique_tag}_2",
        content="Terrible catastrophic failure in the system caused significant damage.",
        published_at=now.replace(tzinfo=None),
        sentiment_label="negative",
        sentiment_score=-0.6,
    )
    db.add(a1)
    db.add(a2)
    db.commit()

    try:
        # Query trend for this specific tag
        response = client.get(f"/api/v1/analytics/trend?query={unique_tag}&days=7")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

        today_str = now.strftime("%Y-%m-%d")
        matching_day = next((item for item in data if item["date"] == today_str), None)
        assert matching_day is not None
        assert matching_day["article_count"] == 2
        # Average of 0.8 and -0.6 is 0.1
        assert abs(matching_day["average_sentiment"] - 0.1) < 0.001
        assert matching_day["positive_count"] == 1
        assert matching_day["negative_count"] == 1
    finally:
        db.delete(a1)
        db.delete(a2)
        db.commit()
        db.close()


def test_trend_endpoint_no_matches():
    response = client.get("/api/v1/analytics/trend?query=non_existent_topic_xyz_12345&days=7")
    assert response.status_code == 200
    assert response.json() == []

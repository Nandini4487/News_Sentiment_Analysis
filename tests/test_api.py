from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_list_articles_empty_ok():
    response = client.get("/api/v1/articles")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_analytics_shape():
    response = client.get("/api/v1/analytics")
    body = response.json()
    for key in ["total_articles", "positive_count", "negative_count", "neutral_count", "average_sentiment_score"]:
        assert key in body


def test_fetch_requires_query_field():
    response = client.post("/api/v1/fetch", json={})
    assert response.status_code == 422
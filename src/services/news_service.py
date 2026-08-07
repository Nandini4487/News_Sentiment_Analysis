from datetime import datetime
from typing import List, Dict, Any

import requests

from src.core.config import settings


class NewsServiceError(Exception):
    pass


class NewsService:
    def __init__(self):
        self.base_url = settings.NEWS_API_BASE_URL
        self.api_key = settings.NEWS_API_KEY

    def fetch_articles(self, query: str, page_size: int = 20) -> List[Dict[str, Any]]:
        endpoint = f"{self.base_url}/everything"
        params = {
            "q": query,
            "pageSize": page_size,
            "language": "en",
            "sortBy": "publishedAt",
            "apiKey": self.api_key,
        }

        response = requests.get(endpoint, params=params, timeout=10)
        if response.status_code != 200:
            raise NewsServiceError(
                f"NewsAPI request failed ({response.status_code}): {response.text}"
            )

        data = response.json()
        articles = []
        for item in data.get("articles", []):
            published_raw = item.get("publishedAt")
            published_at = None
            if published_raw:
                try:
                    published_at = datetime.fromisoformat(published_raw.replace("Z", "+00:00"))
                except ValueError:
                    published_at = None

            articles.append({
                "title": item.get("title") or "Untitled",
                "source": (item.get("source") or {}).get("name"),
                "url": item.get("url"),
                "content": item.get("content") or item.get("description") or "",
                "published_at": published_at,
            })

        return articles


news_service = NewsService()
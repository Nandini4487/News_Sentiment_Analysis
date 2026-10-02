from typing import List, Any
import json
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "News Sentiment API"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    DATABASE_URL: str

    NEWS_API_KEY: str
    NEWS_API_BASE_URL: str = "https://newsapi.org/v2"

    # Scheduler settings
    SCHEDULER_ENABLED: bool = True
    SCHEDULER_INTERVAL_HOURS: int = 1
    SCHEDULER_TOPICS: List[str] = ["technology", "business", "science"]

    @field_validator("SCHEDULER_TOPICS", mode="before")
    @classmethod
    def parse_scheduler_topics(cls, v: Any) -> Any:
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [topic.strip() for topic in v.split(",") if topic.strip()]
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


settings = Settings()
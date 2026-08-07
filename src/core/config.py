from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_NAME: str = "News Sentiment API"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    DATABASE_URL: str

    NEWS_API_KEY: str
    NEWS_API_BASE_URL: str = "https://newsapi.org/v2"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


settings = Settings()
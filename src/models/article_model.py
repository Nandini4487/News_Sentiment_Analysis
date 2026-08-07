from sqlalchemy import Column, Integer, String, Text, Float, DateTime
from sqlalchemy.sql import func
from src.core.database import Base


class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), nullable=False)
    source = Column(String(200), nullable=True)
    url = Column(String(1000), unique=True, nullable=False, index=True)
    content = Column(Text, nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)

    sentiment_label = Column(String(20), nullable=True)   # positive / negative / neutral
    sentiment_score = Column(Float, nullable=True)         # -1.0 to 1.0

    created_at = Column(DateTime(timezone=True), server_default=func.now())
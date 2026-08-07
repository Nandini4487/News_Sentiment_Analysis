from fastapi import FastAPI

from src.core.config import settings
from src.core.database import Base, engine
from src.api.v1.router import api_router

Base.metadata.create_all(bind=engine)  # use Alembic migrations in production

app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG)
app.include_router(api_router, prefix="/api/v1")


@app.get("/", tags=["Health"])
def health_check():
    return {"status": "ok", "app": settings.APP_NAME, "environment": settings.ENVIRONMENT}
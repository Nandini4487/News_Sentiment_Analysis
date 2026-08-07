from fastapi import APIRouter

from src.api.v1 import endpoints

api_router = APIRouter()
api_router.include_router(endpoints.router, tags=["Articles"])
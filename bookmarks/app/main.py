from fastapi import FastAPI
from fastapi import APIRouter

from app.routers import health


app = FastAPI(title="bookmarks")


app.include_router(health.router)


router = APIRouter(tags=["health"])

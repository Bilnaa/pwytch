from contextlib import asynccontextmanager
from typing import AsyncIterator
from fastapi import FastAPI

from app.routers import health, bookmarks
from app.database import engine
from app.models import Base


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    Base.metadata.create_all(engine)

    yield
    engine.dispose()

app = FastAPI(title="bookmarks", lifespan=lifespan)

app.include_router(health.router)
app.include_router(bookmarks.router)

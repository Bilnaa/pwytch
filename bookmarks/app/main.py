from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from common.errors import register_internal_error_handler
from fastapi import FastAPI

from app.database import engine
from app.models import Base
from app.routers import bookmarks, health


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    Base.metadata.create_all(engine)

    yield
    engine.dispose()

app = FastAPI(title="bookmarks", lifespan=lifespan)
register_internal_error_handler(app)

app.include_router(health.router)
app.include_router(bookmarks.router)

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.exc import SQLAlchemyError

from app import cache, events
from app.db import engine, init_db
from app.routers import health, live_chat

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Connects in the background: the service starts even if the broker is down
    await events.mqtt.start()
    # Service starts even if Postgres is down as init_db is retried on the first message
    try:
        await init_db()
    except SQLAlchemyError:
        logger.warning("Database unavailable at startup, live_chat schema not created yet")
    yield
    await events.wait_pending()
    await events.mqtt.stop()
    await cache.redis.aclose()
    await engine.dispose()


app = FastAPI(title="live-chat", lifespan=lifespan)

app.include_router(health.router)
app.include_router(live_chat.router)


@app.get("/")
def root():
    return {"service": "live-chat"}

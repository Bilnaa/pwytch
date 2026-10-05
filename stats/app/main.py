import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from common.errors import register_internal_error_handler
from common.events import SearchHit
from common.mqtt import MqttClient
from common.topics import SEARCH_HIT
from fastapi import FastAPI
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.schema import CreateSchema

from app.config import settings
from app.database import engine
from app.handlers import on_search_hit
from app.models import SCHEMA_NAME, Base
from app.routers import health, search

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        async with engine.begin() as connection:
            if engine.dialect.name == "postgresql":
                await connection.execute(CreateSchema(SCHEMA_NAME, if_not_exists=True))
            await connection.run_sync(Base.metadata.create_all)
    except SQLAlchemyError:
        logger.warning("Database unavailable at startup, %s schema not created yet", SCHEMA_NAME)
    client = MqttClient(host=settings.mqtt_host, port=settings.mqtt_port, client_id="stats")

    client.subscribe(SEARCH_HIT, SearchHit, on_search_hit)
    await client.start()
    try:
        yield
    finally:
        await client.stop()
        await engine.dispose()


app = FastAPI(title="stats", lifespan=lifespan)
register_internal_error_handler(app)

app.include_router(health.router)
app.include_router(search.router)


@app.get("/")
def root():
    return {"service": "stats"}

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from common.mqtt import MqttClient
from fastapi import FastAPI
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.schema import CreateSchema

from app.config import settings
from app.database import engine
from app.models import SCHEMA_NAME, Base
from app.routers import health

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
        logger.warning("Database unavailable at startup, live_chat schema not created yet")
    client = MqttClient(host=settings.mqtt_host, port=settings.mqtt_port, client_id="stats")

    await client.start()
    try:
        yield
    finally:
        await client.stop()
        await engine.dispose()


app = FastAPI(title="stats", lifespan=lifespan)

app.include_router(health.router)


@app.get("/")
def root():
    return {"service": "stats"}

import logging
from typing import AsyncIterator

from common.mqtt import MqttClient
from fastapi import FastAPI
from contextlib import asynccontextmanager

from sqlalchemy import text

from app.routers import health
from app.database import engine
from app.models import SCHEMA_NAME, Base
from app.config import settings


logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with engine.begin() as connection:
        if engine.dialect.name == "postgresql":
            await connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA_NAME}"))
        await connection.run_sync(Base.metadata.create_all)

    client = MqttClient(host=settings.mqtt_host, port=settings.mqtt_port, client_id="stats")

    await client.start()
    yield

    await client.stop()
    await engine.dispose()

    
app = FastAPI(title="stats", lifespan=lifespan)

app.include_router(health.router)


@app.get("/")
def root():
    return {"service": "stats"}

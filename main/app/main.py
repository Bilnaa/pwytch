import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from app import models  # noqa: F401  (registers tables on Base.metadata)
from app.config import stream_settings
from app.db import Base, engine
from app.mqtt import create_mqtt_client
from app.routers import auth, health, lives, streams

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    app.state.stream_client = httpx.AsyncClient(
        base_url=stream_settings.stream_url,
        timeout=stream_settings.stream_timeout_seconds,
    )
    app.state.mqtt = create_mqtt_client()
    # connects in the background: the API starts even if the broker is down
    await app.state.mqtt.start()
    yield
    await app.state.mqtt.stop()
    await app.state.stream_client.aclose()


app = FastAPI(title="main", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(health.router)
app.include_router(streams.router)
app.include_router(lives.router)


@app.get("/")
def root():
    return {"service": "main"}

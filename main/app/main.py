import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import models  # noqa: F401  (registers tables on Base.metadata)
from app.config import cors_settings, search_settings, stream_settings
from app.db import Base, engine
from app.mqtt import create_mqtt_client
from app.routers import auth, health, ingest, lives, search, streams

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    app.state.stream_client = httpx.AsyncClient(
        base_url=stream_settings.stream_url,
        timeout=stream_settings.stream_timeout_seconds,
    )
    app.state.search_client = httpx.AsyncClient(
        base_url=search_settings.search_url,
        timeout=search_settings.search_timeout_seconds,
    )
    app.state.mqtt = create_mqtt_client()
    # connects in the background: the API starts even if the broker is down
    await app.state.mqtt.start()
    yield
    await app.state.mqtt.stop()
    await app.state.search_client.aclose()
    await app.state.stream_client.aclose()


app = FastAPI(title="main", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[cors_settings.frontend_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(health.router)
app.include_router(ingest.router)
app.include_router(streams.router)
app.include_router(lives.router)
app.include_router(search.router)


@app.get("/")
def root():
    return {"service": "main"}

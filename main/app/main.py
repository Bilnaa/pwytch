import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from app import models  # noqa: F401  (registers tables on Base.metadata)
from app.config import (
    cors_settings,
    replay_settings,
    search_settings,
    stats_settings,
    stream_settings,
)
from app.db import Base, engine
from app.mqtt import create_mqtt_client
from app.routers import auth, health, ingest, lives, search, streams
from app.services.satellites import SatelliteError, SatelliteRejectedError

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
    app.state.replay_client = httpx.AsyncClient(
        base_url=replay_settings.replay_url,
        timeout=replay_settings.replay_timeout_seconds,
    )
    app.state.stats_client = httpx.AsyncClient(
        base_url=stats_settings.stats_url,
        timeout=stats_settings.stats_timeout_seconds,
    )
    app.state.mqtt = create_mqtt_client()
    # connects in the background: the API starts even if the broker is down
    await app.state.mqtt.start()
    yield
    await app.state.mqtt.stop()
    await app.state.stats_client.aclose()
    await app.state.replay_client.aclose()
    await app.state.search_client.aclose()
    await app.state.stream_client.aclose()


app = FastAPI(title="main", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[cors_settings.frontend_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)



@app.exception_handler(SatelliteRejectedError)
async def relay_satellite_rejection(request: Request, exc: SatelliteRejectedError):
    return Response(exc.content, status_code=exc.status_code, media_type=exc.media_type)


@app.exception_handler(SatelliteError)
async def satellite_error(request: Request, exc: SatelliteError):
    return JSONResponse({"detail": str(exc)}, status_code=exc.status_code)


app.include_router(auth.router)
app.include_router(health.router)
app.include_router(ingest.router)
app.include_router(streams.router)
app.include_router(lives.router)
app.include_router(search.router)


@app.get("/")
def root():
    return {"service": "main"}

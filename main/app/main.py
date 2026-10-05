import asyncio
import logging
import os
from contextlib import asynccontextmanager, suppress

import httpx
from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from app import models  # noqa: F401  (registers tables on Base.metadata)
from app.config import (
    cors_settings,
    frontend_settings,
    live_chat_settings,
    replay_settings,
    search_settings,
    stats_settings,
    stream_settings,
)
from app.db import Base, SessionLocal, engine
from app.mqtt import create_mqtt_client
from app.routers import auth, chat, health, ingest, lives, replays, search, streams, users
from app.services import streams as streams_service
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
    app.state.live_chat_client = httpx.AsyncClient(
        base_url=live_chat_settings.live_chat_url,
        timeout=live_chat_settings.live_chat_timeout_seconds,
    )
    app.state.mqtt = create_mqtt_client()
    # connects in the background: the API starts even if the broker is down
    await app.state.mqtt.start()
    missed_ends = asyncio.create_task(
        streams_service.watch_missed_ends(app.state.stream_client, SessionLocal)
    )
    yield
    missed_ends.cancel()
    with suppress(asyncio.CancelledError):
        await missed_ends
    await app.state.mqtt.stop()
    await app.state.live_chat_client.aclose()
    await app.state.stats_client.aclose()
    await app.state.replay_client.aclose()
    await app.state.search_client.aclose()
    await app.state.stream_client.aclose()


app = FastAPI(
    title="main",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

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


# everything under /api, the rest of the URLs belong to the front
api = APIRouter(prefix="/api")
api.include_router(auth.router)
api.include_router(health.router)
api.include_router(ingest.router)
api.include_router(chat.router)
api.include_router(streams.router)
api.include_router(lives.router)
api.include_router(search.router)
api.include_router(replays.router)
api.include_router(users.router)


@api.get("")
def root():
    return {"service": "main"}


app.include_router(api)

# only checked when no API route matched; unknown paths get index.html for react-router.
# skipped when the front was not built (tests, Docker image without web/)
if os.path.isdir(frontend_settings.frontend_dir):
    app.frontend("/", directory=frontend_settings.frontend_dir)

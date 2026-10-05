import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from app.conversion import Mp4Converter
from app.infra.config import settings
from app.infra.db import engine, session_factory, try_init_db
from app.mqtt import create_mqtt_client
from app.routers import health, replays


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    # Base coupée : le service démarre quand même, les tables seront créées au redémarrage.
    await try_init_db(engine)
    app.state.converter = Mp4Converter(
        session_factory, settings.stream_url, settings.replays_dir, settings.conversion_timeout_s
    )
    await app.state.converter.reset_interrupted()
    # Sert à vérifier la playlist d'un live terminé en erreur.
    app.state.stream_client = httpx.AsyncClient(
        base_url=settings.stream_url, timeout=settings.stream_timeout_s
    )
    app.state.mqtt = create_mqtt_client(settings, session_factory, app.state.stream_client)
    await app.state.mqtt.start()
    yield
    await app.state.mqtt.stop()
    await app.state.stream_client.aclose()
    await engine.dispose()


app = FastAPI(title="replay", lifespan=lifespan)

app.include_router(health.router)
app.include_router(replays.router)


@app.get("/")
def root():
    return {"service": "replay"}

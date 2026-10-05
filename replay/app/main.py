import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.consumers.mqtt import create_mqtt_client
from app.core.config import settings
from app.core.db import engine, session_factory, try_init_db
from app.routers import health, replays
from app.routers.error_handlers import register_error_handlers
from app.services.conversion_service import Mp4Converter


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    # Base coupée : le service démarre quand même, les tables seront créées au redémarrage.
    await try_init_db(engine)
    app.state.converter = Mp4Converter(
        session_factory, settings.lives_dir, settings.replays_dir, settings.conversion_timeout_s
    )
    await app.state.converter.reset_interrupted()
    app.state.mqtt = create_mqtt_client(settings, session_factory)
    await app.state.mqtt.start()
    yield
    await app.state.mqtt.stop()
    await engine.dispose()


app = FastAPI(title="replay", lifespan=lifespan)

app.include_router(health.router)
app.include_router(replays.router)
register_error_handlers(app)


@app.get("/")
def root():
    return {"service": "replay"}

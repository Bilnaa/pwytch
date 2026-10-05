from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from common.errors import register_internal_error_handler
from common.mqtt import MqttClient
from fastapi import FastAPI

from app.config import settings
from app.database import engine
from app.models import Base
from app.routers import bookmarks, health


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    Base.metadata.create_all(engine)

    app.state.mqtt = MqttClient(host=settings.mqtt_host, port=settings.mqtt_port, client_id="bookmarks")
    await app.state.mqtt.start()

    try:
        yield
    finally:
        await app.state.mqtt.stop()
        engine.dispose()


app = FastAPI(title="bookmarks", lifespan=lifespan)
register_internal_error_handler(app)

app.include_router(health.router)
app.include_router(bookmarks.router)

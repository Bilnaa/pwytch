import logging
from contextlib import asynccontextmanager

from common.errors import register_internal_error_handler
from fastapi import FastAPI

from app.consumers.mqtt import create_mqtt_client
from app.core.config import settings
from app.core.db import engine, init_db, session_factory
from app.routers import health, search


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    # Même engine et même fabrique de sessions que get_session : un seul pool.
    await init_db(engine)
    app.state.mqtt = create_mqtt_client(settings, session_factory)
    await app.state.mqtt.start()
    yield
    await app.state.mqtt.stop()
    await engine.dispose()


app = FastAPI(title="search", lifespan=lifespan)
register_internal_error_handler(app)

app.include_router(health.router)
app.include_router(search.router)


@app.get("/")
def root():
    return {"service": "search"}

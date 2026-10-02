import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.infra.config import settings
from app.infra.db import engine, init_db, session_factory
from app.mqtt import create_mqtt_client
from app.routers import health, search


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    # Même engine et même fabrique de sessions que get_session : un seul pool.
    await init_db(engine)
    # Gardé dans app.state pour publier plus tard (#101).
    app.state.mqtt = create_mqtt_client(settings, session_factory)
    # Connexion en tâche de fond : l'API démarre même si le broker est coupé.
    await app.state.mqtt.start()
    yield
    await app.state.mqtt.stop()
    await engine.dispose()


app = FastAPI(title="search", lifespan=lifespan)

app.include_router(health.router)
app.include_router(search.router)


@app.get("/")
def root():
    return {"service": "search"}

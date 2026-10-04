import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.infra.db import engine, init_db
from app.routers import health


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    await init_db(engine)
    yield
    await engine.dispose()


app = FastAPI(title="replay", lifespan=lifespan)

app.include_router(health.router)


@app.get("/")
def root():
    return {"service": "replay"}

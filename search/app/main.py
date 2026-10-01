import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from app.consumer import run_consumer
from app.infra.config import settings
from app.infra.db import engine, init_db, session_factory
from app.routers import health, search


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    # Même engine et même fabrique de sessions que get_session : un seul pool.
    await init_db(engine)
    consumer_task = asyncio.create_task(run_consumer(settings, session_factory))
    yield
    consumer_task.cancel()
    with suppress(asyncio.CancelledError):
        await consumer_task
    await engine.dispose()


app = FastAPI(title="search", lifespan=lifespan)

app.include_router(health.router)
app.include_router(search.router)


@app.get("/")
def root():
    return {"service": "search"}

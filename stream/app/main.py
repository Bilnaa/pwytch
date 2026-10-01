from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import live
from app.routers import health, ingest


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await live.close_all()


app = FastAPI(title="stream", lifespan=lifespan)

app.include_router(health.router)
app.include_router(ingest.router)


@app.get("/")
def root():
    return {"service": "stream"}

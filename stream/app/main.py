from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import events, live
from app.routers import health, ingest, lives


@asynccontextmanager
async def lifespan(app: FastAPI):
    # connects in the background: the service starts even if the broker is down
    await events.mqtt.start()
    yield
    # the lives that are closed here still publish their stream/ended
    await live.close_all()
    await events.mqtt.stop()


app = FastAPI(title="stream", lifespan=lifespan)

app.include_router(health.router)
app.include_router(ingest.router)
app.include_router(lives.router)


@app.get("/")
def root():
    return {"service": "stream"}

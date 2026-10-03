import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import events, live, recovery
from app.config import settings
from app.routers import health, ingest, lives, streams


@asynccontextmanager
async def lifespan(app: FastAPI):
    # connects in the background: the service starts even if the broker is down
    await events.mqtt.start()
    # lives cut by a restart: the playlists are ended now, the events wait for the broker
    ended = recovery.end_interrupted_lives(settings.lives_dir)
    recovering = asyncio.create_task(recovery.publish_ended(ended))
    yield
    recovering.cancel()
    # the lives that are closed here still publish their stream/ended
    await live.close_all()
    await events.mqtt.stop()


app = FastAPI(title="stream", lifespan=lifespan)

app.include_router(health.router)
app.include_router(ingest.router)
app.include_router(lives.router)
app.include_router(streams.router)


@app.get("/")
def root():
    return {"service": "stream"}

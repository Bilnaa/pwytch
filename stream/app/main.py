import mimetypes
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import hls
from app.config import settings
from app.routers import health, ingest, lives

# python:3.12-slim doesn't know .ts and some systems send .m3u8 as application/x-mpegurl
mimetypes.add_type("application/vnd.apple.mpegurl", ".m3u8")
mimetypes.add_type("video/mp2t", ".ts")


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await hls.close_all()


app = FastAPI(title="stream", lifespan=lifespan)

app.include_router(health.router)
app.include_router(ingest.router)

# StaticFiles refuses to start if the folder doesn't exist yet
settings.lives_dir.mkdir(parents=True, exist_ok=True)
lives_files = StaticFiles(directory=settings.lives_dir)
app.mount("/lives", lives_files, name="lives")
# must come after the mount, see routers/lives.py
app.include_router(lives.router)


@app.get("/")
def root():
    return {"service": "stream"}

import shutil

from fastapi import APIRouter

from app import events

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    ready = shutil.which("ffmpeg") is not None and events.mqtt.connected
    # still 200 when degraded: the service answers, it just can't do everything
    return {"status": "ok" if ready else "degraded"}

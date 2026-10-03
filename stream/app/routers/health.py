import shutil

from fastapi import APIRouter

from app import events

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    # still 200 when degraded: the service answers, it just can't do everything
    if shutil.which("ffmpeg") is None:
        return {"status": "degraded"}
    if not events.mqtt.connected:
        return {"status": "degraded"}
    return {"status": "ok"}

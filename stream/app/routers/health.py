import shutil

from fastapi import APIRouter

from app import events
from app.live import lives

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    ffmpeg = shutil.which("ffmpeg") is not None
    broker = events.mqtt.connected
    return {
        # still 200 when degraded: the service answers, it just can't do everything
        "status": "ok" if ffmpeg and broker else "degraded",
        "ffmpeg": ffmpeg,
        "broker": broker,
        "lives": sum(1 for live in lives.values() if not live.ending),
    }

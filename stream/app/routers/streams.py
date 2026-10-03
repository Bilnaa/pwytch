from fastapi import APIRouter

from app.live import lives

router = APIRouter(tags=["streams"])


@router.get("/streams", summary="List the lives that are not over yet")
def list_streams() -> list[int]:
    # a live waiting for its streamer counts, one that is ending doesn't
    return sorted(stream_id for stream_id, live in lives.items() if not live.ending)

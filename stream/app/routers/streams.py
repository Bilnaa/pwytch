from fastapi import APIRouter

from app.live import lives

router = APIRouter(tags=["streams"])


@router.get("/streams", summary="List the lives that are not over yet")
async def list_streams() -> list[int]:
    # async so it runs on the event loop: the lives add and remove themselves from the dict there
    stream_ids = []
    for stream_id, live in lives.items():
        # a live waiting for its streamer counts, one that is ending doesn't
        if live.ending is None:
            stream_ids.append(stream_id)
    stream_ids.sort()
    return stream_ids

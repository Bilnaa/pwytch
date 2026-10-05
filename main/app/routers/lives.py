from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Path
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from app.dependencies import get_stream_client
from app.services import lives as lives_service

router = APIRouter(tags=["lives"])

PLAYLIST_TYPE = "application/vnd.apple.mpegurl"


@router.get(
    "/lives/{stream_id}/{filename}",
    summary="Relay the playlist or a segment of a live from stream",
    responses={
        200: {
            "description": "`index.m3u8` or `index{N}.ts`",
            "content": {PLAYLIST_TYPE: {}, "video/mp2t": {}},
        },
        404: {"description": "Live or file not found"},
        502: {"description": "stream gave an invalid answer"},
        503: {"description": "stream is unavailable"},
        504: {"description": "stream took too long to answer"},
    },
)
async def get_live_file(
    stream_id: int,
    filename: Annotated[str, Path(pattern=r"^index\d*\.(m3u8|ts)$")],
    client: Annotated[httpx.AsyncClient, Depends(get_stream_client)],
):
    live_file = await lives_service.open_live_file(client, stream_id, filename)
    return StreamingResponse(
        live_file.content,
        media_type=live_file.media_type,
        headers={"Cache-Control": live_file.cache_control},
        background=BackgroundTask(live_file.close),
    )

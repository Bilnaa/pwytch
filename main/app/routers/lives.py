from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Path, Request
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

router = APIRouter(tags=["lives"])

PLAYLIST_TYPE = "application/vnd.apple.mpegurl"


def get_stream_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.stream_client


@router.get(
    "/lives/{stream_id}/{filename}",
    summary="Relay the playlist or a segment of a live from stream",
    responses={
        200: {
            "description": "`index.m3u8` or `index{N}.ts`",
            "content": {PLAYLIST_TYPE: {}, "video/mp2t": {}},
        },
        404: {"description": "Live or file not found"},
        503: {"description": "stream is unavailable"},
        504: {"description": "stream took too long to answer"},
    },
)
async def get_live_file(
    stream_id: int,
    filename: Annotated[str, Path(pattern=r"^index\d*\.(m3u8|ts)$")],
    client: Annotated[httpx.AsyncClient, Depends(get_stream_client)],
):
    request = client.build_request("GET", f"/lives/{stream_id}/{filename}")
    try:
        upstream = await client.send(request, stream=True)
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="stream timed out") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail="stream is unavailable") from exc

    if upstream.status_code != 200:
        await upstream.aclose()
        if upstream.status_code == 404:
            raise HTTPException(status_code=404, detail="Live or file not found")
        raise HTTPException(status_code=502, detail="Invalid answer from stream")

    # the playlist changes during the live, segments never do
    if filename.endswith(".m3u8"):
        cache_control = "no-cache"
    else:
        cache_control = "public, max-age=3600"

    return StreamingResponse(
        upstream.aiter_bytes(),
        media_type=upstream.headers.get("content-type"),
        headers={"Cache-Control": cache_control},
        background=BackgroundTask(upstream.aclose),
    )

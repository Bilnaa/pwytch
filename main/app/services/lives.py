from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass

import httpx

from app.services import satellites


@dataclass
class LiveFile:
    content: AsyncIterator[bytes]
    media_type: str | None
    cache_control: str
    close: Callable[[], Awaitable[None]]


def get_cache_control(filename: str) -> str:
    # the playlist changes during the live, segments never do
    if filename.endswith(".m3u8"):
        return "no-cache"
    return "public, max-age=3600"


async def open_live_file(
    client: httpx.AsyncClient, stream_id: int, filename: str
) -> LiveFile:
    upstream = await satellites.send(
        client, "GET", f"/lives/{stream_id}/{filename}", stream=True
    )
    return LiveFile(
        content=upstream.aiter_bytes(),
        media_type=upstream.headers.get("content-type"),
        cache_control=get_cache_control(filename),
        close=upstream.aclose,
    )

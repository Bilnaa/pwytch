from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass

import httpx
from pydantic import TypeAdapter

from app.config import replay_settings
from app.schemas.replay import ReplayPage, ReplayResponse
from app.services import satellites

REPLAY_PAGE = TypeAdapter(ReplayPage)
REPLAY = TypeAdapter(ReplayResponse)
RELAYED_DOWNLOAD_HEADERS = ("content-disposition", "retry-after")


@dataclass
class ReplayDownload:
    content: AsyncIterator[bytes]
    status_code: int
    media_type: str | None
    headers: dict[str, str]
    close: Callable[[], Awaitable[None]]


async def list_replays(
    client: httpx.AsyncClient, page: int, size: int, streamer_id: int | None
) -> ReplayPage:
    params = {"page": page, "size": size}
    if streamer_id is not None:
        params["streamer_id"] = streamer_id
    response = await satellites.send(client, "GET", "/replays", params=params)
    return satellites.parse(response, REPLAY_PAGE)


async def get_replay(client: httpx.AsyncClient, stream_id: int) -> ReplayResponse:
    response = await satellites.send(client, "GET", f"/replays/{stream_id}")
    return satellites.parse(response, REPLAY)


async def open_replay_download(client: httpx.AsyncClient, stream_id: int) -> ReplayDownload:
    upstream = await satellites.send(
        client,
        "GET",
        f"/replays/{stream_id}/download",
        stream=True,
        timeout=httpx.Timeout(
            replay_settings.replay_timeout_seconds,
            read=replay_settings.replay_download_timeout_seconds,
        ),
        relayed_errors={500},
    )
    return ReplayDownload(
        content=upstream.aiter_bytes(),
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type"),
        headers={
            name: upstream.headers[name]
            for name in RELAYED_DOWNLOAD_HEADERS
            if name in upstream.headers
        },
        close=upstream.aclose,
    )

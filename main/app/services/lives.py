from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass

import httpx


class LiveFileNotFoundError(Exception):
    pass


class StreamTimeoutError(Exception):
    pass


class StreamUnavailableError(Exception):
    pass


class InvalidStreamResponseError(Exception):
    pass


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
    request = client.build_request("GET", f"/lives/{stream_id}/{filename}")
    try:
        upstream = await client.send(request, stream=True)
    except httpx.TimeoutException as exc:
        raise StreamTimeoutError("stream timed out") from exc
    except httpx.HTTPError as exc:
        raise StreamUnavailableError("stream is unavailable") from exc

    if upstream.status_code != 200:
        await upstream.aclose()
        if upstream.status_code == 404:
            raise LiveFileNotFoundError("Live or file not found")
        raise InvalidStreamResponseError("Invalid answer from stream")

    return LiveFile(
        content=upstream.aiter_bytes(),
        media_type=upstream.headers.get("content-type"),
        cache_control=get_cache_control(filename),
        close=upstream.aclose,
    )

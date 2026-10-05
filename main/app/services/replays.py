import httpx
from pydantic import TypeAdapter

from app.schemas.replay import ReplayPage, ReplayResponse
from app.services import satellites

REPLAY_PAGE = TypeAdapter(ReplayPage)
REPLAY = TypeAdapter(ReplayResponse)


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

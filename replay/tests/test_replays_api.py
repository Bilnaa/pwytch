from datetime import timedelta

import pytest

from tests.factories import FIRST_END, add_replay


async def get_replays(client, **params):
    response = await client.get("/replays", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def stream_ids(body) -> list[int]:
    return [item["stream_id"] for item in body["items"]]


# Liste


@pytest.mark.anyio
async def test_list_is_sorted_from_the_most_recent_end(client, session):
    await add_replay(session, 1, ended_at=FIRST_END)
    await add_replay(session, 2, ended_at=FIRST_END + timedelta(hours=2))
    await add_replay(session, 3, ended_at=FIRST_END + timedelta(hours=1))

    body = await get_replays(client)

    assert stream_ids(body) == [2, 3, 1]
    assert body["total"] == 3
    assert (body["page"], body["size"]) == (1, 20)


@pytest.mark.anyio
async def test_same_end_is_ordered_by_stream_id_desc(client, session):
    await add_replay(session, 1)
    await add_replay(session, 2)

    assert stream_ids(await get_replays(client)) == [2, 1]


@pytest.mark.anyio
async def test_live_in_progress_is_not_listed(client, session):
    await add_replay(session, 1)
    await add_replay(session, 2, ended_at=None, duration_s=None)

    body = await get_replays(client)

    assert stream_ids(body) == [1]
    assert body["total"] == 1


@pytest.mark.anyio
async def test_pagination_returns_the_requested_page(client, session):
    for stream_id in range(1, 6):
        await add_replay(session, stream_id, ended_at=FIRST_END + timedelta(minutes=stream_id))

    body = await get_replays(client, page=2, size=2)

    assert stream_ids(body) == [3, 2]
    assert body["total"] == 5


@pytest.mark.anyio
async def test_page_after_the_end_is_empty(client, session):
    await add_replay(session, 1)

    body = await get_replays(client, page=3, size=1)

    assert body["items"] == []
    assert body["total"] == 1


@pytest.mark.anyio
async def test_filter_by_streamer(client, session):
    await add_replay(session, 1, streamer_id=7)
    await add_replay(session, 2, streamer_id=8)

    body = await get_replays(client, streamer_id=8)

    assert stream_ids(body) == [2]
    assert body["total"] == 1


@pytest.mark.anyio
@pytest.mark.parametrize(
    "params",
    [{"page": 0}, {"size": 0}, {"size": 51}, {"streamer_id": 0}, {"streamer_id": 2147483648}],
    ids=["page-zero", "size-zero", "size-too-big", "streamer-zero", "streamer-above-int32"],
)
async def test_invalid_list_params_return_422(client, params):
    response = await client.get("/replays", params=params)

    assert response.status_code == 422


# Détail


@pytest.mark.anyio
async def test_detail_has_exact_fields(client, session):
    await add_replay(session, 42)

    response = await client.get("/replays/42")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "stream_id",
        "streamer_id",
        "streamer_name",
        "title",
        "game",
        "started_at",
        "ended_at",
        "duration_s",
        "mp4_status",
        "playback_url",
    }
    assert body["stream_id"] == 42
    assert body["title"] == "Speedrun Any%"
    assert body["duration_s"] == 5400.0
    assert body["mp4_status"] == "none"
    assert body["playback_url"] == "/lives/42/index.m3u8"


@pytest.mark.anyio
async def test_replay_without_started_has_null_infos(client, session):
    await add_replay(session, 42, streamer_name=None, title=None, game=None, started_at=None)

    body = (await client.get("/replays/42")).json()

    assert [body[field] for field in ["streamer_name", "title", "game", "started_at"]] == [
        None,
        None,
        None,
        None,
    ]


@pytest.mark.anyio
async def test_unknown_replay_returns_404(client):
    response = await client.get("/replays/999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Replay not found"}


@pytest.mark.anyio
async def test_live_in_progress_returns_404(client, session):
    await add_replay(session, 42, ended_at=None, duration_s=None)

    response = await client.get("/replays/42")

    assert response.status_code == 404


@pytest.mark.anyio
@pytest.mark.parametrize(
    "stream_id", ["abc", "0", "2147483648"], ids=["text", "zero", "above-int32"]
)
async def test_invalid_stream_id_returns_422(client, stream_id):
    response = await client.get(f"/replays/{stream_id}")

    assert response.status_code == 422

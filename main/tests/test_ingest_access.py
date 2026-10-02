import pytest
from starlette.websockets import WebSocketDisconnect

from app.models import Stream
from tests.fakes import close_code, create_stream


def test_missing_or_bad_token_closes_with_4401(client, upstream):
    stream_id, _ = create_stream(client)

    assert close_code(client, f"/streams/{stream_id}/ingest?token=nope") == 4401
    assert upstream.urls == []


def test_missing_token_is_rejected(client, upstream):
    stream_id, _ = create_stream(client)

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/streams/{stream_id}/ingest"):
            pass


def test_other_streamer_closes_with_4403(client, upstream):
    stream_id, _ = create_stream(client, "alice")
    _, bob_token = create_stream(client, "bob")

    assert close_code(client, f"/streams/{stream_id}/ingest?token={bob_token}") == 4403
    assert upstream.urls == []


def test_unknown_stream_closes_with_4404(client, upstream):
    _, token = create_stream(client)

    assert close_code(client, f"/streams/999/ingest?token={token}") == 4404


@pytest.mark.parametrize("status", ["ended", "cancelled"])
def test_finished_stream_closes_with_4409(client, db_session, upstream, status):
    stream_id, token = create_stream(client)
    db_session.get(Stream, stream_id).status = status
    db_session.commit()

    assert close_code(client, f"/streams/{stream_id}/ingest?token={token}") == 4409
    assert upstream.urls == []

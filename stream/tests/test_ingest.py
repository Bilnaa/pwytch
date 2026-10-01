import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app import hls
from app.config import settings
from app.main import app
from app.routers.ingest import active_streams


@pytest.fixture
def procs(tmp_path, monkeypatch):
    """Fake ffmpeg: one mock process per live, nothing is launched."""
    monkeypatch.setattr(settings, "lives_dir", tmp_path)
    created = []

    async def spawn(*args, **kwargs):
        async def wait():
            await asyncio.sleep(0.05)  # takes time, like the real one
            return proc.returncode or 0

        proc = MagicMock(returncode=None, wait=AsyncMock(side_effect=wait))
        proc.stdin.drain = AsyncMock()
        proc.stdin.wait_closed = AsyncMock()
        proc.stdin.is_closing.return_value = False
        proc.stderr.__aiter__.return_value = [b"Invalid data found\n"]
        created.append(proc)
        return proc

    monkeypatch.setattr(hls.asyncio, "create_subprocess_exec", spawn)
    return created


def written(proc):
    return [c.args[0] for c in proc.stdin.write.call_args_list]


def wait_until_finished(stream_id):
    deadline = time.monotonic() + 5
    while stream_id in active_streams and time.monotonic() < deadline:
        time.sleep(0.01)


def test_each_live_gets_its_own_ffmpeg(procs):
    with TestClient(app) as client:
        with client.websocket_connect("/streams/1/ingest") as live1, \
             client.websocket_connect("/streams/2/ingest") as live2:
            live1.send_bytes(b"a1")
            live2.send_bytes(b"b1")
            live1.send_bytes(b"a2")
            live1.close()
            live2.close()
            wait_until_finished(1)
            wait_until_finished(2)

    assert [written(p) for p in procs] == [[b"a1", b"a2"], [b"b1"]]
    for proc in procs:
        proc.stdin.close.assert_called_once()  # makes ffmpeg write #EXT-X-ENDLIST


def test_ffmpeg_crash_closes_websocket_and_frees_the_stream(procs, caplog):
    with TestClient(app) as client:
        with client.websocket_connect("/streams/7/ingest") as ws:
            procs[0].returncode = 1  # ffmpeg died
            ws.send_bytes(b"garbage")
            with pytest.raises(WebSocketDisconnect) as exc:
                ws.receive_bytes()
        wait_until_finished(7)

        assert exc.value.code == 1011
        assert 7 not in active_streams
        assert client.get("/health").status_code == 200

    assert "Invalid data found" in caplog.text  # ffmpeg's stderr is logged


def test_same_stream_twice_is_refused(procs):
    with TestClient(app) as client:
        with client.websocket_connect("/streams/5/ingest") as ws:
            with client.websocket_connect("/streams/5/ingest") as other:
                with pytest.raises(WebSocketDisconnect) as exc:
                    other.receive_bytes()
            ws.close()
            wait_until_finished(5)

    assert exc.value.code == 1008
    assert len(procs) == 1


def test_reconnect_on_a_finished_live_is_refused(procs):
    with TestClient(app) as client:
        with client.websocket_connect("/streams/3/ingest") as ws:
            ws.close()
        wait_until_finished(3)
        with client.websocket_connect("/streams/3/ingest") as ws:
            with pytest.raises(WebSocketDisconnect) as exc:
                ws.receive_bytes()

    assert exc.value.code == 1008
    assert len(procs) == 1  # no second ffmpeg writing over the replay


def test_shutdown_mid_stream_still_closes_ffmpeg(procs):
    with TestClient(app) as client:
        with client.websocket_connect("/streams/9/ingest") as ws:
            ws.send_bytes(b"chunk")
        # leaving the blocks cancels the handler, then shuts the app down

    procs[0].stdin.close.assert_called_once()
    procs[0].wait.assert_awaited()

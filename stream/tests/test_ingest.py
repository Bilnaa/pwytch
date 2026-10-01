import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app import hls, live
from app.config import settings
from app.main import app


@pytest.fixture
def procs(tmp_path, monkeypatch):
    """Fake ffmpeg: one mock process per run, nothing is launched."""
    monkeypatch.setattr(settings, "lives_dir", tmp_path)
    monkeypatch.setattr(settings, "reconnect_seconds", 0.1)
    created = []

    async def spawn(*args, **kwargs):
        async def wait():
            await asyncio.sleep(0.05)  # takes time, like the real one
            return proc.returncode or 0

        proc = MagicMock(returncode=None, wait=AsyncMock(side_effect=wait))
        proc.is_slate = str(hls.SLATE) in args
        proc.stdin.drain = AsyncMock()
        proc.stdin.wait_closed = AsyncMock()
        proc.stdin.is_closing.return_value = False
        proc.stderr.__aiter__.return_value = [b"Invalid data found\n"]
        created.append(proc)
        return proc

    monkeypatch.setattr(hls.asyncio, "create_subprocess_exec", spawn)
    return created


def streamer(procs):
    return [p for p in procs if not p.is_slate]


def slate(procs):
    return [p for p in procs if p.is_slate]


def written(proc):
    return [c.args[0] for c in proc.stdin.write.call_args_list]


def wait_until(condition):
    deadline = time.monotonic() + 5
    while not condition() and time.monotonic() < deadline:
        time.sleep(0.01)


def wait_until_finished(stream_id):
    wait_until(lambda: stream_id not in live.lives)


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

    assert [written(p) for p in streamer(procs)] == [[b"a1", b"a2"], [b"b1"]]
    for proc in procs:
        proc.stdin.close.assert_called_once()


def test_ffmpeg_crash_closes_websocket_and_frees_the_stream(procs, caplog):
    with TestClient(app) as client:
        with client.websocket_connect("/streams/7/ingest") as ws:
            procs[0].returncode = 1  # ffmpeg died
            ws.send_bytes(b"garbage")
            with pytest.raises(WebSocketDisconnect) as exc:
                ws.receive_bytes()
        wait_until_finished(7)

        assert exc.value.code == 1011
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
    assert len(streamer(procs)) == 1


def test_reconnect_during_grace_period_goes_on(procs, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "reconnect_seconds", 5)
    with TestClient(app) as client:
        with client.websocket_connect("/streams/4/ingest") as ws:
            ws.send_bytes(b"part1")
            ws.close()
        wait_until(lambda: slate(procs))  # viewers see "signal lost"
        with client.websocket_connect("/streams/4/ingest") as ws:
            ws.send_bytes(b"part2")
            ws.close()

    assert [written(p) for p in streamer(procs)] == [[b"part1"], [b"part2"]]
    assert written(slate(procs)[0]) == [b"q"]  # slate stopped when the streamer came back


def test_silent_streamer_is_treated_as_a_cut(procs, monkeypatch):
    monkeypatch.setattr(settings, "signal_timeout_seconds", 0.1)
    with TestClient(app) as client:
        with client.websocket_connect("/streams/11/ingest") as ws:
            ws.send_bytes(b"chunk")
            with pytest.raises(WebSocketDisconnect) as exc:
                ws.receive_bytes()
        wait_until_finished(11)

    assert exc.value.code == 1013
    assert written(streamer(procs)[0]) == [b"chunk"]
    assert written(slate(procs)[0]) == [b"q"]  # viewers got "signal lost", then the live ended


def test_live_ends_after_grace_period(procs, tmp_path):
    with TestClient(app) as client:
        with client.websocket_connect("/streams/3/ingest") as ws:
            (tmp_path / "3" / "index.m3u8").write_text("#EXTM3U\n")  # written by ffmpeg for real
            ws.close()
        wait_until_finished(3)
        with client.websocket_connect("/streams/3/ingest") as ws:
            with pytest.raises(WebSocketDisconnect) as exc:
                ws.receive_bytes()

    assert (tmp_path / "3" / "index.m3u8").read_text() == "#EXTM3U\n#EXT-X-ENDLIST\n"
    assert written(slate(procs)[0]) == [b"q"]
    assert exc.value.code == 1008  # the replay is never written over
    assert len(streamer(procs)) == 1


def test_http_ingest_goes_through_the_same_live(procs):
    with TestClient(app) as client:
        assert client.post("/streams/6/ingest", content=b"video").status_code == 204
        wait_until_finished(6)
        again = client.post("/streams/6/ingest", content=b"video")

    assert again.status_code == 409
    assert [written(p) for p in streamer(procs)] == [[b"video"]]
    assert written(slate(procs)[0]) == [b"q"]


def test_http_ingest_is_refused_while_the_websocket_is_live(procs):
    with TestClient(app) as client:
        with client.websocket_connect("/streams/8/ingest") as ws:
            response = client.post("/streams/8/ingest", content=b"video")
            ws.close()
            wait_until_finished(8)

    assert response.status_code == 409
    assert response.json() == {"detail": "Stream already live"}


def test_http_ingest_ffmpeg_crash_returns_500(procs, monkeypatch):
    monkeypatch.setattr(hls.HlsPipeline, "write", AsyncMock(side_effect=hls.HlsError))
    with TestClient(app) as client:
        response = client.post("/streams/10/ingest", content=b"garbage")
        wait_until_finished(10)

    assert response.status_code == 500
    procs[0].stdin.close.assert_called_once()  # ffmpeg is still closed properly


def test_shutdown_mid_stream_still_closes_ffmpeg(procs):
    with TestClient(app) as client:
        with client.websocket_connect("/streams/9/ingest") as ws:
            ws.send_bytes(b"chunk")
        # leaving the blocks cancels the handler, then shuts the app down

    procs[0].stdin.close.assert_called_once()
    procs[0].wait.assert_awaited()
    assert 9 not in live.lives

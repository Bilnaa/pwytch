from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app import hls, live
from app.config import settings
from app.main import app
from tests.helpers import ingest_url, slate, streamer, wait_until, wait_until_finished, written


def test_each_live_gets_its_own_ffmpeg(procs):
    with TestClient(app) as client:
        with client.websocket_connect(ingest_url(1)) as live1, \
             client.websocket_connect(ingest_url(2)) as live2:
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
        with client.websocket_connect(ingest_url(7)) as ws:
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
        with client.websocket_connect(ingest_url(5)) as ws:
            with client.websocket_connect(ingest_url(5)) as other:
                with pytest.raises(WebSocketDisconnect) as exc:
                    other.receive_bytes()
            ws.close()
            wait_until_finished(5)

    assert exc.value.code == 1008
    assert len(streamer(procs)) == 1


def test_reconnect_during_grace_period_goes_on(procs, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "reconnect_seconds", 5)
    with TestClient(app) as client:
        with client.websocket_connect(ingest_url(4)) as ws:
            ws.send_bytes(b"part1")
            ws.close()
        wait_until(lambda: slate(procs))  # viewers see "signal lost"
        with client.websocket_connect(ingest_url(4)) as ws:
            ws.send_bytes(b"part2")
            ws.close()

    assert [written(p) for p in streamer(procs)] == [[b"part1"], [b"part2"]]
    assert written(slate(procs)[0]) == [b"q"]  # slate stopped when the streamer came back


def test_silent_streamer_is_treated_as_a_cut(procs, monkeypatch):
    monkeypatch.setattr(settings, "signal_timeout_seconds", 0.1)
    with TestClient(app) as client:
        with client.websocket_connect(ingest_url(11)) as ws:
            ws.send_bytes(b"chunk")
            with pytest.raises(WebSocketDisconnect) as exc:
                ws.receive_bytes()
        wait_until_finished(11)

    assert exc.value.code == 1013
    assert written(streamer(procs)[0]) == [b"chunk"]
    assert written(slate(procs)[0]) == [b"q"]  # viewers got "signal lost", then the live ended


def test_live_ends_after_grace_period(procs, tmp_path):
    with TestClient(app) as client:
        with client.websocket_connect(ingest_url(3)) as ws:
            (tmp_path / "3" / "index.m3u8").write_text("#EXTM3U\n")  # written by ffmpeg for real
            ws.close()
        wait_until_finished(3)
        with client.websocket_connect(ingest_url(3)) as ws:
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
        with client.websocket_connect(ingest_url(8)) as ws:
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
        with client.websocket_connect(ingest_url(9)) as ws:
            ws.send_bytes(b"chunk")
        # leaving the blocks cancels the handler, then shuts the app down

    procs[0].stdin.close.assert_called_once()
    procs[0].wait.assert_awaited()
    assert 9 not in live.lives

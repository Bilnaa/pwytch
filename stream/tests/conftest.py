import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app import events, hls, live
from app.config import settings


@pytest.fixture(autouse=True)
def mqtt(monkeypatch):
    """Fake MQTT client: no broker is needed, the published events stay on the mock."""
    fake = AsyncMock()
    monkeypatch.setattr(events, "mqtt", fake)
    return fake


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
    monkeypatch.setattr(live, "probe_size", AsyncMock(return_value=None))
    return created

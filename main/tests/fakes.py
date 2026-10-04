import asyncio

import pytest
from starlette.websockets import WebSocketDisconnect

from tests.test_streams_router import PAYLOAD, auth_headers


class FakeUpstream:
    """Stands for the WebSocket of stream, so the tests don't need the real service."""

    def __init__(
        self,
        close_after_send=False,
        send_error=None,
        connect_error=None,
        close_code=1008,
        close_reason="Stream already live",
    ):
        self.chunks = []
        self.urls = []
        self.close_code = None
        self.close_reason = ""
        self.close_after_send = close_after_send
        self.closing = (close_code, close_reason)
        self.send_error = send_error
        self.connect_error = connect_error
        self.entered = False
        self.exited = False
        self._closed = None

    def __call__(self, url, **kwargs):
        self.urls.append(url)
        return self

    async def __aenter__(self):
        if self.connect_error:
            raise self.connect_error
        self._closed = asyncio.Event()
        self.entered = True
        return self

    async def __aexit__(self, *exc):
        self.exited = True

    async def send(self, chunk):
        if self.send_error:
            raise self.send_error
        self.chunks.append(chunk)
        if self.close_after_send:
            self.close_code, self.close_reason = self.closing
            self._closed.set()

    async def wait_closed(self):
        await self._closed.wait()


class FakeChat:
    def __init__(self, messages=(), close_after_send=False, connect_error=None, close_error=None):
        self.urls = []
        self.sent = []
        self.messages = list(messages)
        self.close_after_send = close_after_send
        self.connect_error = connect_error
        self.close_error = close_error
        self.exited = False
        self._closed = None

    def __call__(self, url, **kwargs):
        self.urls.append(url)
        return self

    async def __aenter__(self):
        if self.connect_error:
            raise self.connect_error
        self._closed = asyncio.Event()
        return self

    async def __aexit__(self, *exc):
        self.exited = True

    async def send(self, message):
        self.sent.append(message)
        if self.close_after_send:
            self._closed.set()

    def __aiter__(self):
        return self.receive()

    async def receive(self):
        for message in self.messages:
            yield message
        await self._closed.wait()
        if self.close_error:
            raise self.close_error


def create_stream(client, username="alice"):
    headers = auth_headers(client, username)
    response = client.post("/streams", json=PAYLOAD, headers=headers)
    return response.json()["id"], headers["Authorization"].removeprefix("Bearer ")


def close_code(client, path):
    with client.websocket_connect(path) as ws:
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_bytes()
    return exc.value.code

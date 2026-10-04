from typing import Annotated

import anyio
import httpx
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import TypeAdapter

from app.db import get_db
from app.dependencies import get_optional_user
from app.main import relay_satellite_rejection, satellite_error
from app.models import User
from app.services import satellites
from app.services.auth import create_access_token, register

# no route calls a satellite with the user yet: mount one on a test-only app
app = FastAPI()
app.add_exception_handler(satellites.SatelliteRejectedError, relay_satellite_rejection)
app.add_exception_handler(satellites.SatelliteError, satellite_error)


def get_satellite_client() -> httpx.AsyncClient:
    raise NotImplementedError


@app.get("/relay")
async def relay(
    client: Annotated[httpx.AsyncClient, Depends(get_satellite_client)],
    user: Annotated[User | None, Depends(get_optional_user)],
):
    response = await satellites.send(client, "GET", "/things", user=user)
    return response.json()


@pytest.fixture
def use_satellite(db_session):
    clients = []

    def use(handler):
        satellite = httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="http://satellite"
        )
        clients.append(satellite)
        app.dependency_overrides[get_satellite_client] = lambda: satellite

    app.dependency_overrides[get_db] = lambda: db_session
    yield use
    app.dependency_overrides.clear()
    for client in clients:
        anyio.run(client.aclose)


@pytest.fixture
def client():
    return TestClient(app)


def echo_identity(request):
    names = ("x-user-id", "x-user-name", "x-user-role")
    return httpx.Response(200, json={name: request.headers.get(name) for name in names})


def test_identity_headers_are_sent_for_a_logged_in_user(client, use_satellite, db_session):
    user = register(db_session, "John_Doe", "s3cret-pass")
    use_satellite(echo_identity)

    token = create_access_token(user)
    response = client.get("/relay", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == {
        "x-user-id": str(user.id),
        "x-user-name": "john_doe",
        "x-user-role": "user",
    }


def test_no_identity_headers_without_token(client, use_satellite):
    use_satellite(echo_identity)

    response = client.get("/relay")

    assert response.status_code == 200
    assert response.json() == {"x-user-id": None, "x-user-name": None, "x-user-role": None}


def test_invalid_token_returns_401(client, use_satellite):
    def handler(request):
        raise AssertionError("satellite should not be called")

    use_satellite(handler)
    response = client.get("/relay", headers={"Authorization": "Bearer nope"})
    assert response.status_code == 401


@pytest.mark.parametrize("status_code", [400, 403, 404, 409, 422])
def test_client_error_is_relayed_as_is(client, use_satellite, status_code):
    use_satellite(
        lambda request: httpx.Response(
            status_code,
            content=b'{"detail":"from satellite"}',
            headers={"content-type": "application/json"},
        )
    )

    response = client.get("/relay")

    assert response.status_code == status_code
    assert response.content == b'{"detail":"from satellite"}'
    assert response.headers["content-type"] == "application/json"


@pytest.mark.parametrize("status_code", [500, 503, 302])
def test_unexpected_status_returns_502(client, use_satellite, status_code):
    use_satellite(lambda request: httpx.Response(status_code))
    response = client.get("/relay")
    assert response.status_code == 502
    assert response.json() == {"detail": "Invalid answer from service"}


def test_unreachable_satellite_returns_503(client, use_satellite):
    def handler(request):
        raise httpx.ConnectError("refused")

    use_satellite(handler)
    response = client.get("/relay")
    assert response.status_code == 503
    assert response.json() == {"detail": "Service is unavailable"}


def test_timeout_returns_504(client, use_satellite):
    def handler(request):
        raise httpx.ReadTimeout("too slow")

    use_satellite(handler)
    response = client.get("/relay")
    assert response.status_code == 504
    assert response.json() == {"detail": "Service timed out"}


def satellite_client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://satellite")


@pytest.mark.anyio
async def test_send_passes_params_and_json():
    def handler(request):
        assert request.method == "POST"
        assert request.url.path == "/things"
        assert dict(request.url.params) == {"page": "2"}
        assert request.content == b'{"name":"x"}'
        return httpx.Response(201)

    async with satellite_client(handler) as client:
        response = await satellites.send(
            client, "POST", "/things", params={"page": 2}, json={"name": "x"}
        )

    assert response.status_code == 201


@pytest.mark.anyio
async def test_streamed_client_error_keeps_its_body():
    async with satellite_client(lambda request: httpx.Response(404, content=b"missing")) as client:
        with pytest.raises(satellites.SatelliteRejectedError) as exc_info:
            await satellites.send(client, "GET", "/things", stream=True)

    assert exc_info.value.status_code == 404
    assert exc_info.value.content == b"missing"


@pytest.mark.anyio
async def test_parse_validates_the_body():
    async with satellite_client(lambda request: httpx.Response(200, json=[1, 2])) as client:
        response = await satellites.send(client, "GET", "/things")

    assert satellites.parse(response, TypeAdapter(list[int])) == [1, 2]
    with pytest.raises(satellites.InvalidSatelliteResponseError):
        satellites.parse(response, TypeAdapter(list[str]))

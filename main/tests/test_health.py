import anyio
import httpx
import pytest
from sqlalchemy.exc import OperationalError

from app.dependencies import (
    get_live_chat_client,
    get_mqtt,
    get_replay_client,
    get_search_client,
    get_stats_client,
    get_stream_client,
)
from app.main import app

SATELLITES = {
    "stream": get_stream_client,
    "search": get_search_client,
    "replay": get_replay_client,
    "stats": get_stats_client,
    "live-chat": get_live_chat_client,
}


class FakeMqtt:
    def __init__(self, connected=True):
        self.connected = connected


def healthy(request):
    return httpx.Response(200, json={"status": "ok"})


def provide(satellite):
    return lambda: satellite


@pytest.fixture
def use_services():
    clients = []

    def use(connected=True, **handlers):
        app.dependency_overrides[get_mqtt] = lambda: FakeMqtt(connected)
        for name, dependency in SATELLITES.items():
            satellite = httpx.AsyncClient(
                transport=httpx.MockTransport(handlers.get(name, healthy)),
                base_url=f"http://{name}",
            )
            clients.append(satellite)
            app.dependency_overrides[dependency] = provide(satellite)

    yield use
    for client in clients:
        anyio.run(client.aclose)


def test_everything_is_up(client, use_services):
    use_services()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database": "ok",
        "broker": "ok",
        "satellites": {
            "stream": "ok",
            "search": "ok",
            "replay": "ok",
            "stats": "ok",
            "live-chat": "ok",
        },
    }


def test_satellites_are_checked_on_their_health_route(client, use_services):
    paths = []

    def handler(request):
        paths.append(request.url.path)
        return healthy(request)

    use_services(stream=handler)
    client.get("/health")

    assert paths == ["/health"]


def test_a_down_satellite_does_not_fail_the_route(client, use_services):
    def refused(request):
        raise httpx.ConnectError("refused")

    use_services(search=refused, replay=lambda request: httpx.Response(500))

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["satellites"] == {
        "stream": "ok",
        "search": "down",
        "replay": "down",
        "stats": "ok",
        "live-chat": "ok",
    }


def test_a_timed_out_satellite_is_down(client, use_services):
    def too_slow(request):
        raise httpx.ReadTimeout("too slow")

    use_services(stats=too_slow)

    assert client.get("/health").json()["satellites"]["stats"] == "down"


def test_a_degraded_satellite_is_reported(client, use_services):
    use_services(stream=lambda request: httpx.Response(200, json={"status": "degraded"}))

    body = client.get("/health").json()

    assert body["status"] == "degraded"
    assert body["satellites"]["stream"] == "degraded"


def test_an_invalid_satellite_answer_is_down(client, use_services):
    use_services(stream=lambda request: httpx.Response(200, json={"status": "maybe"}))

    assert client.get("/health").json()["satellites"]["stream"] == "down"


def test_a_disconnected_broker_is_down(client, use_services):
    use_services(connected=False)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["broker"] == "down"


def test_a_down_database_is_reported(client, use_services, db_session, monkeypatch):
    def fail(*args, **kwargs):
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    monkeypatch.setattr(db_session, "execute", fail)
    use_services()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["database"] == "down"

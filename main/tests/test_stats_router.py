import anyio
import httpx
import pytest

from app.dependencies import get_stats_client
from app.main import app
from app.services.auth import make_admin
from tests.test_streams_router import auth_headers

COUNTER = {"item_type": "streamer", "item_id": "42", "count": 3}
BOOKMARK_DELETED = {"target_type": "replay", "target_id": 7, "count": 2}
CHAT_MESSAGES = {"stream_id": 12, "count": 40}
PLAYER_EVENTS = {"stream_id": 12, "play": 5, "pause": 2, "stop": 1}


@pytest.fixture
def use_stats():
    clients = []

    def use(handler):
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://stats")
        clients.append(client)
        app.dependency_overrides[get_stats_client] = lambda: client

    yield use
    for client in clients:
        anyio.run(client.aclose)


@pytest.fixture
def admin_headers(client, db_session):
    headers = auth_headers(client, "admin_user")
    make_admin(db_session, "admin_user")
    return headers


def never_called(request):
    raise AssertionError("stats should not be called")


def test_count_is_relayed_with_identity(client, use_stats, admin_headers):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=COUNTER)

    use_stats(handler)
    response = client.get("/stats/search/streamer/42", headers=admin_headers)

    assert response.status_code == 200
    assert response.json() == COUNTER
    assert requests[0].url.path == "/stats/search/streamer/42"
    assert requests[0].headers["x-user-role"] == "admin"


def test_top_is_relayed_with_default_limit(client, use_stats, admin_headers):
    def handler(request):
        assert request.url.path == "/stats/search/top"
        assert dict(request.url.params) == {"limit": "10"}
        return httpx.Response(200, json=[COUNTER])

    use_stats(handler)
    response = client.get("/stats/search/top", headers=admin_headers)

    assert response.status_code == 200
    assert response.json() == [COUNTER]


def test_top_relays_limit_and_item_type(client, use_stats, admin_headers):
    def handler(request):
        assert dict(request.url.params) == {"limit": "5", "item_type": "message"}
        return httpx.Response(200, json=[])

    use_stats(handler)
    response = client.get(
        "/stats/search/top", params={"limit": 5, "item_type": "message"}, headers=admin_headers
    )

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize(
    "path, sent_params, answer",
    [
        ("/stats/bookmarks/deleted/replay/7", {}, BOOKMARK_DELETED),
        ("/stats/bookmarks/deleted/top", {"limit": "10"}, [BOOKMARK_DELETED]),
        ("/stats/chat/12", {}, CHAT_MESSAGES),
        ("/stats/chat/top", {"limit": "10"}, [CHAT_MESSAGES]),
        ("/stats/player/12", {}, PLAYER_EVENTS),
    ],
)
def test_other_stats_are_relayed(client, use_stats, admin_headers, path, sent_params, answer):
    def handler(request):
        assert request.url.path == path
        assert dict(request.url.params) == sent_params
        return httpx.Response(200, json=answer)

    use_stats(handler)
    response = client.get(path, headers=admin_headers)

    assert response.status_code == 200
    assert response.json() == answer


def test_bookmarks_top_relays_limit_and_target_type(client, use_stats, admin_headers):
    def handler(request):
        assert dict(request.url.params) == {"limit": "5", "target_type": "streamer"}
        return httpx.Response(200, json=[])

    use_stats(handler)
    response = client.get(
        "/stats/bookmarks/deleted/top",
        params={"limit": 5, "target_type": "streamer"},
        headers=admin_headers,
    )

    assert response.status_code == 200


@pytest.mark.parametrize(
    "path",
    [
        "/stats/search/top?limit=0",
        "/stats/search/top?limit=501",
        "/stats/search/top?item_type=replay",
        "/stats/search/replay/42",
        "/stats/bookmarks/deleted/top?target_type=message",
        "/stats/bookmarks/deleted/message/7",
        "/stats/bookmarks/deleted/replay/0",
        "/stats/chat/top?limit=501",
        "/stats/chat/2147483648",
        "/stats/player/0",
    ],
)
def test_invalid_params_are_not_relayed(client, use_stats, admin_headers, path):
    use_stats(never_called)
    assert client.get(path, headers=admin_headers).status_code == 422


@pytest.mark.parametrize(
    "path",
    ["/stats/search/top", "/stats/bookmarks/deleted/top", "/stats/chat/top", "/stats/player/12"],
)
def test_user_gets_403(client, use_stats, path):
    use_stats(never_called)
    response = client.get(path, headers=auth_headers(client))

    assert response.status_code == 403
    assert response.json() == {"detail": "Admin role required"}


@pytest.mark.parametrize("path", ["/stats/search/top", "/stats/search/streamer/42"])
def test_without_token_gets_401(client, use_stats, path):
    use_stats(never_called)
    assert client.get(path).status_code == 401


def test_unavailable_stats_gives_503(client, use_stats, admin_headers):
    def handler(request):
        raise httpx.ConnectError("refused")

    use_stats(handler)
    response = client.get("/stats/search/top", headers=admin_headers)

    assert response.status_code == 503


def test_invalid_answer_gives_502(client, use_stats, admin_headers):
    use_stats(lambda request: httpx.Response(200, json={"count": "many"}))
    response = client.get("/stats/search/streamer/42", headers=admin_headers)

    assert response.status_code == 502

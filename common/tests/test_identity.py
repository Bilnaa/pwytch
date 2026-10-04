import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from common.identity import CurrentUser, UserIdentity, to_headers

app = FastAPI()


@app.get("/me")
def read_me(user: CurrentUser) -> UserIdentity:
    return user


client = TestClient(app)
user = UserIdentity(id=42, name="Zerator", role="streamer")


def test_to_headers_writes_all_fields_as_strings():
    assert to_headers(user) == {
        "X-User-Id": "42",
        "X-User-Name": "Zerator",
        "X-User-Role": "streamer",
    }


def test_dependency_reads_user_from_headers():
    response = client.get("/me", headers=to_headers(user))

    assert response.status_code == 200
    assert response.json() == {"id": 42, "name": "Zerator", "role": "streamer"}


@pytest.mark.parametrize("missing", ["X-User-Id", "X-User-Name", "X-User-Role"])
def test_missing_header_returns_401(missing):
    headers = to_headers(user)
    del headers[missing]

    response = client.get("/me", headers=headers)

    assert response.status_code == 401


@pytest.mark.parametrize("user_id", ["abc", "42.0", "+42", "4_2", "-1", "0"])
def test_invalid_id_returns_401(user_id):
    response = client.get("/me", headers={**to_headers(user), "X-User-Id": user_id})

    assert response.status_code == 401


@pytest.mark.parametrize("empty", ["X-User-Name", "X-User-Role"])
def test_empty_name_or_role_returns_401(empty):
    response = client.get("/me", headers={**to_headers(user), empty: ""})

    assert response.status_code == 401

def test_get_user_returns_the_public_profile(client):
    client.post("/auth/register", json={"username": "Alice_42", "password": "s3cret-pass"})

    response = client.get("/users/ALICE_42")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"id", "username", "display_name"}
    assert body["username"] == "alice_42"
    assert body["display_name"] == "Alice_42"


def test_unknown_user_returns_404(client):
    response = client.get("/users/nobody")

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


def register(client, username):
    payload = {"username": username, "password": "s3cret-pass"}
    return client.post("/auth/register", json=payload).json()


def test_list_users_by_id_skips_unknown_ids(client):
    first = register(client, "bob_1")
    second = register(client, "carol_2")

    response = client.get(f"/users?id={second['id']}&id={first['id']}&id=999")

    assert response.status_code == 200
    assert [user["username"] for user in response.json()] == ["bob_1", "carol_2"]


def test_list_users_needs_an_id(client):
    response = client.get("/users")

    assert response.status_code == 422

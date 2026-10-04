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

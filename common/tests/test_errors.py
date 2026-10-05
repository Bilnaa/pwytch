from fastapi import FastAPI
from fastapi.testclient import TestClient

from common.errors import register_internal_error_handler

app = FastAPI()
register_internal_error_handler(app)


@app.get("/boom")
def boom():
    raise RuntimeError("unexpected")


def test_unexpected_exception_returns_json_500():
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/boom")

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from common.errors import ErrorResponse, register_error_handlers, register_internal_error_handler

app = FastAPI()
register_error_handlers(app)


@app.get("/boom")
def boom():
    raise RuntimeError("unexpected")


@app.get("/missing")
def missing():
    raise HTTPException(status_code=404, detail="Replay not found")


@app.get("/protected")
def protected():
    raise HTTPException(status_code=401, headers={"WWW-Authenticate": "Bearer"})


@app.get("/items/{item_id}")
def item(item_id: int):
    return {"id": item_id}


client = TestClient(app, raise_server_exceptions=False)


def test_unexpected_exception_returns_internal_error():
    response = client.get("/boom")

    assert response.status_code == 500
    assert response.json() == {
        "error": {"code": "internal_error", "message": "Internal server error"}
    }


def test_http_exception_keeps_its_message():
    response = client.get("/missing")

    assert response.status_code == 404
    assert response.json() == {"error": {"code": "not_found", "message": "Replay not found"}}


def test_http_exception_without_detail_uses_status_phrase_and_keeps_headers():
    response = client.get("/protected")

    assert response.status_code == 401
    assert response.json() == {"error": {"code": "unauthorized", "message": "Unauthorized"}}
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_unknown_route_returns_not_found():
    response = client.get("/nowhere")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_validation_error_returns_first_message():
    response = client.get("/items/abc")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert "integer" in response.json()["error"]["message"]


def test_responses_match_error_response_model():
    ErrorResponse.model_validate(client.get("/missing").json())


def test_internal_error_handler_alone_leaves_http_errors_untouched():
    partial = FastAPI()
    register_internal_error_handler(partial)

    @partial.get("/missing")
    def partial_missing():
        raise HTTPException(status_code=404, detail="Not here")

    response = TestClient(partial).get("/missing")

    assert response.json() == {"detail": "Not here"}

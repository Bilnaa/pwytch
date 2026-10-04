import logging
from typing import Any

import httpx
from common.identity import UserIdentity, to_headers
from pydantic import TypeAdapter, ValidationError

from app.models import User

logger = logging.getLogger(__name__)


class SatelliteError(Exception):
    status_code = 502


class InvalidSatelliteResponseError(SatelliteError):
    status_code = 502


class SatelliteUnavailableError(SatelliteError):
    status_code = 503


class SatelliteTimeoutError(SatelliteError):
    status_code = 504


class SatelliteRejectedError(SatelliteError):
    def __init__(self, response: httpx.Response):
        super().__init__(f"Satellite answered {response.status_code}")
        self.status_code = response.status_code
        self.content = response.content
        self.media_type = response.headers.get("content-type")


def identity_headers(user: User | None) -> dict[str, str]:
    if user is None:
        return {}
    return to_headers(UserIdentity(id=user.id, name=user.username, role=user.role))


async def send(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    *,
    user: User | None = None,
    params: dict[str, Any] | None = None,
    json: Any = None,
    stream: bool = False,
) -> httpx.Response:
    request = client.build_request(
        method, path, params=params, json=json, headers=identity_headers(user)
    )
    try:
        response = await client.send(request, stream=stream)
    except httpx.TimeoutException as exc:
        logger.warning("%s %s timed out", method, request.url)
        raise SatelliteTimeoutError("Service timed out") from exc
    except httpx.HTTPError as exc:
        logger.warning("%s %s failed: %s", method, request.url, exc)
        raise SatelliteUnavailableError("Service is unavailable") from exc

    if response.is_success:
        return response

    if stream:
        await response.aread()
        await response.aclose()
    if response.is_client_error and response.status_code != 401:
        raise SatelliteRejectedError(response)
    logger.warning("%s %s answered %s", method, request.url, response.status_code)
    raise InvalidSatelliteResponseError("Invalid answer from service")


def parse[T](response: httpx.Response, adapter: TypeAdapter[T]) -> T:
    try:
        return adapter.validate_json(response.content)
    except ValidationError as exc:
        logger.warning("%s answered an invalid body: %s", response.request.url, exc)
        raise InvalidSatelliteResponseError("Invalid answer from service") from exc

import httpx
from pydantic import ValidationError

from app.schemas.search import StreamerPage


class InvalidSearchQueryError(Exception):
    def __init__(self, detail):
        super().__init__("Invalid search query")
        self.detail = detail


class SearchTimeoutError(Exception):
    pass


class SearchUnavailableError(Exception):
    pass


class InvalidSearchResponseError(Exception):
    pass


async def search_streamers(
    client: httpx.AsyncClient, query: str, page: int, size: int
) -> StreamerPage:
    try:
        response = await client.get(
            "/search/streamers", params={"q": query, "page": page, "size": size}
        )
    except httpx.TimeoutException as exc:
        raise SearchTimeoutError("search timed out") from exc
    except httpx.HTTPError as exc:
        raise SearchUnavailableError("search is unavailable") from exc

    if response.status_code == 422:
        try:
            detail = response.json()["detail"]
        except (ValueError, KeyError, TypeError) as exc:
            raise InvalidSearchResponseError("Invalid answer from search") from exc
        raise InvalidSearchQueryError(detail)
    if response.status_code != 200:
        raise InvalidSearchResponseError("Invalid answer from search")

    try:
        return StreamerPage.model_validate_json(response.content)
    except ValidationError as exc:
        raise InvalidSearchResponseError("Invalid answer from search") from exc

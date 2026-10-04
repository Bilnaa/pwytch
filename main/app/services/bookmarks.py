import httpx
from pydantic import TypeAdapter

from app.models import User
from app.schemas.bookmark import BookmarkCreate, BookmarkResponse, BookmarkUpdate
from app.services import satellites

BOOKMARK = TypeAdapter(BookmarkResponse)
BOOKMARK_LIST = TypeAdapter(list[BookmarkResponse])


async def list_bookmarks(client: httpx.AsyncClient, user: User) -> list[BookmarkResponse]:
    response = await satellites.send(client, "GET", "/bookmarks", user=user)
    return satellites.parse(response, BOOKMARK_LIST)


async def create_bookmark(
    client: httpx.AsyncClient, user: User, payload: BookmarkCreate
) -> BookmarkResponse:
    response = await satellites.send(
        client, "POST", "/bookmarks", user=user, json=payload.model_dump(mode="json")
    )
    return satellites.parse(response, BOOKMARK)


async def get_bookmark(
    client: httpx.AsyncClient, user: User, bookmark_id: int
) -> BookmarkResponse:
    response = await satellites.send(client, "GET", f"/bookmarks/{bookmark_id}", user=user)
    return satellites.parse(response, BOOKMARK)


async def update_bookmark(
    client: httpx.AsyncClient, user: User, bookmark_id: int, payload: BookmarkUpdate
) -> BookmarkResponse:
    response = await satellites.send(
        client,
        "PATCH",
        f"/bookmarks/{bookmark_id}",
        user=user,
        json=payload.model_dump(mode="json", exclude_unset=True),
    )
    return satellites.parse(response, BOOKMARK)


async def delete_bookmark(client: httpx.AsyncClient, user: User, bookmark_id: int) -> None:
    await satellites.send(client, "DELETE", f"/bookmarks/{bookmark_id}", user=user)

from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Request, Response, status

from app.dependencies import get_bookmarks_client, get_current_user
from app.models import User
from app.schemas.bookmark import BookmarkCreate, BookmarkResponse, BookmarkUpdate
from app.services import bookmarks as bookmarks_service

router = APIRouter(prefix="/bookmarks", tags=["bookmarks"])

Client = Annotated[httpx.AsyncClient, Depends(get_bookmarks_client)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get("", response_model=list[BookmarkResponse], summary="List my bookmarks")
async def list_bookmarks(client: Client, current_user: CurrentUser):
    return await bookmarks_service.list_bookmarks(client, current_user)


@router.post(
    "",
    response_model=BookmarkResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Bookmark a replay or a streamer",
)
async def create_bookmark(
    payload: BookmarkCreate,
    client: Client,
    current_user: CurrentUser,
    request: Request,
    response: Response,
):
    bookmark = await bookmarks_service.create_bookmark(client, current_user, payload)
    response.headers["Location"] = request.app.url_path_for(
        "get_bookmark", bookmark_id=bookmark.id
    )
    return bookmark


@router.get("/{bookmark_id}", response_model=BookmarkResponse, summary="Get one of my bookmarks")
async def get_bookmark(bookmark_id: int, client: Client, current_user: CurrentUser):
    return await bookmarks_service.get_bookmark(client, current_user, bookmark_id)


@router.patch(
    "/{bookmark_id}", response_model=BookmarkResponse, summary="Edit one of my bookmarks"
)
async def update_bookmark(
    bookmark_id: int, payload: BookmarkUpdate, client: Client, current_user: CurrentUser
):
    return await bookmarks_service.update_bookmark(client, current_user, bookmark_id, payload)


@router.delete(
    "/{bookmark_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete one of my bookmarks",
)
async def delete_bookmark(bookmark_id: int, client: Client, current_user: CurrentUser):
    await bookmarks_service.delete_bookmark(client, current_user, bookmark_id)

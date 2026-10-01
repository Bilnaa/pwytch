from typing import Annotated

from fastapi import Depends
from bookmarks.app import verify_auth
from bookmarks.app.schemas import BookmarkCreate, BookmarkUpdate

from fastapi import APIRouter


router = APIRouter(tags=["health"])


@router.patch("/bookmarks/{bookmark_id}")
async def update_bookmarks(
    bookmark_id: int, 
    bookmark: BookmarkUpdate,
    x_user_id: Annotated[int, Depends(verify_auth)]
) -> dict:
    pass


@router.post("/bookmarks")
async def create_bookmarks(bookmark: BookmarkCreate) -> dict:
    pass


@router.delete("/bookmarks/{bookmark_id}")
async def delete_bookmarks(bookmark_id: int, bookmark: BookmarkUpdate) -> dict:
    pass

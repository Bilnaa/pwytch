from typing import Annotated

from fastapi import Depends, FastAPI

from app.routers import health
from bookmarks.app import verify_auth
from bookmarks.app.models import BookmarkCreate, BookmarkUpdate

app = FastAPI(title="bookmarks")

app.include_router(health.router)


@app.patch("/bookmarks/{bookmark_id}")
async def update_bookmarks(
    bookmark_id: int, 
    bookmark: BookmarkUpdate,
    x_user_id: Annotated[int, Depends(verify_auth)]
) -> dict:
    pass

@app.post("/bookmarks")
async def create_bookmarks(bookmark: BookmarkCreate) -> dict:
    pass

@app.delete("/bookmarks/{bookmark_id}")
async def delete_bookmarks(bookmark_id: int, bookmark: BookmarkUpdate) -> dict:
    pass

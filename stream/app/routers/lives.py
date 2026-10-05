import mimetypes

from fastapi import APIRouter, HTTPException
from fastapi.staticfiles import StaticFiles

from app.config import settings

# python:3.12-slim doesn't know .ts and some systems send .m3u8 as application/x-mpegurl
mimetypes.add_type("application/vnd.apple.mpegurl", ".m3u8")
mimetypes.add_type("video/mp2t", ".ts")

router = APIRouter(tags=["lives"])

# StaticFiles refuses to start if the folder doesn't exist yet
settings.lives_dir.mkdir(parents=True, exist_ok=True)
lives_files = StaticFiles(directory=settings.lives_dir)
router.mount("/lives", lives_files, name="lives")


# never called: the mount above answers first. A mount doesn't show up in /docs, this route does.
@router.get(
    "/lives/{stream_id}/{filename}",
    summary="Get the playlist or a segment of a live",
    responses={
        200: {
            "description": "`index.m3u8` or `index{N}.ts`",
            "content": {"application/vnd.apple.mpegurl": {}, "video/mp2t": {}},
        },
        404: {"description": "File not found"},
    },
)
def get_live_file(stream_id: int, filename: str):
    raise HTTPException(status_code=404)

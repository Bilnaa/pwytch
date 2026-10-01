from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["lives"])


# never called: the /lives mount answers first. A mount doesn't show up in /docs, this route does.
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

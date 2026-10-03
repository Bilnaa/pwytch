from typing import Annotated

from fastapi import APIRouter, Depends, WebSocket
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import ALREADY_ENDED, get_ingest_stream
from app.models import Stream
from app.services import ingest as ingest_service

router = APIRouter(tags=["ingest"])

ALREADY_STREAMING = 4423
UNSUPPORTED_DATA = 1003
INTERNAL_ERROR = 1011
TRY_AGAIN_LATER = 1013


@router.websocket("/streams/{stream_id}/ingest")
async def ingest(
    websocket: WebSocket,
    stream: Annotated[Stream, Depends(get_ingest_stream)],
    db: Annotated[Session, Depends(get_db)],
):
    try:
        await ingest_service.run_ingest(websocket, db, stream)
    except ingest_service.TextFrameError as exc:
        await websocket.close(code=UNSUPPORTED_DATA, reason=str(exc))
    except ingest_service.StreamOverError as exc:
        await websocket.close(code=ALREADY_ENDED, reason=str(exc))
    except ingest_service.StreamAlreadyLiveError as exc:
        await websocket.close(code=ALREADY_STREAMING, reason=str(exc)[:120])
    except ingest_service.SignalLostError as exc:
        await websocket.close(code=TRY_AGAIN_LATER, reason=str(exc)[:120])
    except ingest_service.StreamUnavailableError as exc:
        await websocket.close(code=INTERNAL_ERROR, reason=str(exc)[:120])
    else:
        await websocket.close()

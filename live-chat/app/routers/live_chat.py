import json
import logging

from fastapi import APIRouter, WebSocket
from sqlalchemy.exc import SQLAlchemyError
from starlette.websockets import WebSocketDisconnect

from app.connection_manager import connectionManager
from app.models.message_model import Author, MessageModel
from app.services.messages import save_message

logger = logging.getLogger(__name__)

router = APIRouter(tags=["liveChat"])


@router.websocket("/streams/{stream_id}/chat")
async def live_chat(
    websocket: WebSocket, stream_id: int, user_id: int | None = None, username: str | None = None
):
    username = (username or "").strip()[:50]
    await connectionManager.connect(stream_id, websocket)
    try:
        while True:
            ws_text = await websocket.receive_text()

            # Not sending any message if the user_id isn't in the QueryParams
            if user_id is None or not username:
                await websocket.send_json({
                    "type": "error",
                    "code": "READ_ONLY",
                    "detail": "Utilisateur non identifié",
                })
                continue

            # Checking if the json format is valid
            try:
                data = json.loads(ws_text)
            except ValueError:
                await websocket.send_json({
                    "type": "error",
                    "code": "INVALID_JSON",
                    "detail": "Le JSON est invalide",
                })
                continue

            # If data's type is not a dict
            if not isinstance(data, dict):
                await websocket.send_json({
                    "type": "error",
                    "code": "INVALID_DATA_TYPE",
                    "detail": "Les données envoyées ne sont pas un dict",
                })
                continue

            message = data.get("content", "")

            # If the message content is not a string
            if not isinstance(message, str):
                await websocket.send_json({
                    "type": "error",
                    "code": "INVALID_MESSAGE_TYPE",
                    "detail": "Le message n'est pas une chaine de charactere",
                })
                continue

            message = message.strip()

            # Checking if json is empty
            if message == "":
                await websocket.send_json({
                    "type": "error",
                    "code": "EMPTY_MESSAGE",
                    "detail": "Le message est vide",
                })
                continue

            # Checking if json is too long
            if len(message) > 500:
                await websocket.send_json({
                    "type": "error",
                    "code": "CONTENT_TOO_LONG",
                    "detail": "Le message est trop long",
                })
                continue

            # Checking if a certain amount of seconds passed before sending a new message
            if not connectionManager.can_send_message(user_id, stream_id):
                await websocket.send_json(
                    {"type": "error", "code": "RATE_LIMITED", "detail": "Veuillez attendre une seconde."})
                continue

            author = Author(id=user_id, username=username)
            final_message = MessageModel(stream_id=stream_id, author=author, content=message)

            # Saving before broadcasting: a message that isn't stored is never broadcast
            try:
                await save_message(final_message)
            except SQLAlchemyError:
                logger.exception("Could not save a message of stream %s", stream_id)
                await websocket.send_json({
                    "type": "error",
                    "code": "MESSAGE_NOT_SAVED",
                    "detail": "Le message n'a pas pu être enregistré",
                })
                continue

            await connectionManager.broadcast(stream_id, final_message)

    except WebSocketDisconnect:
        pass

    finally:
        connectionManager.disconnect(stream_id, websocket)

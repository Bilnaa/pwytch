import json

from fastapi import APIRouter, WebSocket
from app.connection_manager import connectionManager

router = APIRouter(tags=["liveChat"])


@router.websocket("/streams/{stream_id}/chat")
async def live_chat(websocket: WebSocket, stream_id: int, user_id: int | None = None, username: str | None = None):
    await connectionManager.connect(stream_id, websocket)
    try:
        while True:
            ws_text = await websocket.receive_text()
            # Not sending any message if the user_id isn't in the QueryParams
            if user_id is None:
                await websocket.send_json({"type": "error", "code": "READ_ONLY", "detail": "Utilisateur sans identifiant"})
                continue

            # Checking if the json format is valid
            try:
                data = json.loads(ws_text)
            except ValueError:
                await websocket.send_json({"type":"error", "code":"INVALID_JSON", "detail":"Le JSON est invalide"})
                continue

            # If data's type is not a dict
            if not isinstance(data, dict):
                await websocket.send_json({"type": "error", "code": "INVALID_DATA_TYPE", "detail": "Les données envoyées ne sont pas un dict"})
                continue

            message = data.get("content", "")

            # If the message content is not a string
            if not isinstance(message, str):
                await websocket.send_json({"type": "error", "code": "INVALID_MESSAGE_TYPE", "detail": "Le message n'est pas une chaine de charactere"})
                continue

            message = message.strip()

            # Checking if json is empty
            if message == "":
                await websocket.send_json({"type": "error", "code": "EMPTY_MESSAGE", "detail": "Le message est vide"})
                continue

            # Checking if json is too long
            if len(message) > 500:
                await websocket.send_json({"type": "error", "code": "CONTENT_TOO_LONG", "detail": "Le message est trop long"})
                continue

            await connectionManager.broadcast(stream_id, message)
    finally:
        connectionManager.disconnect(stream_id, websocket)
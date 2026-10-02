import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.connection_manager import connectionManager

router = APIRouter(tags=["liveChat"])


@router.websocket("/streams/{stream_id}/chat")
async def live_chat(websocket: WebSocket, stream_id: int, user_id: int | None = None, username: str | None = None):
    await connectionManager.connect(stream_id, websocket)
    try:
        while True:
            ws_text = await websocket.receive_text()
            # On envoie pas le message si le user_id n'est pas en queryparams
            if user_id is None:
                await websocket.send_json({"type": "error", "code": "READ_ONLY", "detail": "Utilisateur sans identifiant"})
                continue

            # On regarde si le json du message est invalide
            try:
                data = json.loads(ws_text)
            except ValueError:
                await websocket.send_json({"type":"error", "code":"INVALID_JSON", "detail":"Le JSON est invalide"})
                continue

            # Si data n'est pas un dict
            if type(data) != dict:
                await websocket.send_json({"type": "error", "code": "INVALID_DATA_TYPE", "detail": "Les données envoyées ne sont pas un dict"})
                continue

            message = data.get("content", "")

            # Si le contenu de message n'est pas un str
            if type(message) != str:
                await websocket.send_json({"type": "error", "code": "INVALID_MESSAGE_TYPE", "detail": "Le message n'est pas une chaine de charactere"})
                continue

            message = message.strip()

            # On regarde si le json est vide
            if message == "" or len(message) > 500:
                await websocket.send_json({"type": "error", "code": "EMPTY_OR_LONG_JSON", "detail": "Le JSON est vide ou trop long"})
                continue
            await connectionManager.broadcast(stream_id, message)
    except WebSocketDisconnect:
        connectionManager.disconnect(stream_id, websocket)
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, computed_field

from app.infra.models import Mp4Status


class ReplayResult(BaseModel):
    stream_id: int
    streamer_id: int
    # Nuls si stream/ended est arrivé sans stream/started (voir « Dettes connues »).
    streamer_name: str | None
    title: str | None
    game: str | None
    started_at: datetime | None
    ended_at: datetime
    duration_s: float
    mp4_status: Mp4Status

    @computed_field
    @property
    def playback_url(self) -> str:
        # Relatif à la racine de l'API de main (/api), qui relaie la playlist de stream :
        # le front le passe à apiUrl(), qui ajoute l'origine et /api.
        return f"/lives/{self.stream_id}/index.m3u8"


class ConversionPending(BaseModel):
    """Réponse 202 : le .mp4 n'est pas encore prêt, redemander après Retry-After."""

    stream_id: int
    mp4_status: Literal[Mp4Status.PROCESSING] = Mp4Status.PROCESSING

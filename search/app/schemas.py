from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class StreamerResult(BaseModel):
    streamer_id: int
    streamer_name: str
    last_title: str | None
    last_game: str | None
    is_live: bool
    live_stream_id: int | None


class MessageResult(BaseModel):
    message_id: UUID
    stream_id: int
    author_name: str
    content: str
    sent_at: datetime

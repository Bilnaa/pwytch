from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class BaseEvent(BaseModel):
    event_id: UUID
    version: int = 1


class StreamStarted(BaseEvent):
    stream_id: str
    streamer_id: str
    streamer_name: str
    title: str
    game: str
    started_at: datetime


class StreamEnded(BaseEvent):
    stream_id: str
    streamer_id: str
    ended_at: datetime
    duration_s: int
    reason: Literal["normal", "error"]

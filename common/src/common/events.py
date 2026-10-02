from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID, uuid4

from pydantic import AwareDatetime, BaseModel, Field, StringConstraints


class BaseEvent(BaseModel):
    # consumers drop an event whose event_id they already saw (QoS 1 can deliver twice)
    event_id: UUID = Field(default_factory=uuid4)
    version: int = 1


class StreamStarted(BaseEvent):
    stream_id: int
    streamer_id: int
    streamer_name: str
    title: str
    game: str
    started_at: datetime


class StreamEnded(BaseEvent):
    stream_id: int
    streamer_id: int
    ended_at: datetime
    duration_s: float
    reason: Literal["normal", "error"]


class PlayerEvent(BaseEvent):
    stream_id: int
    event_type: Literal["play", "pause", "stop"]
    user_id: int | None
    occurred_at: datetime


# published by live-chat, consumed by search and stats; message_id is unique across all streams
class ChatMessage(BaseEvent):
    message_id: int
    stream_id: int
    author_id: int
    author_name: str = Field(min_length=1)
    content: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
    ]
    sent_at: AwareDatetime

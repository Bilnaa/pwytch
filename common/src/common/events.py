from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


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

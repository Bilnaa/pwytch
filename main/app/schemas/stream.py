from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

StreamStatus = Literal["created", "live", "ended", "cancelled"]
PlayerEventType = Literal["play", "pause", "stop"]


class StreamCreate(BaseModel):
    title: str = Field(min_length=1, max_length=100, examples=["Speedrun any%"])
    game: str = Field(min_length=1, max_length=50, examples=["Celeste"])


class PlayerEventCreate(BaseModel):
    event_type: PlayerEventType


class Streamer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str = Field(examples=["john_doe"])


class StreamResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    streamer: Streamer
    title: str = Field(examples=["Speedrun any%"])
    game: str = Field(examples=["Celeste"])
    status: StreamStatus
    created_at: datetime
    started_at: datetime | None
    ended_at: datetime | None


class StreamPage(BaseModel):
    items: list[StreamResponse]
    total: int
    page: int
    size: int

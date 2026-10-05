from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class StreamerResult(BaseModel):
    streamer_id: int
    streamer_name: str = Field(examples=["Célèste"])
    last_title: str | None = Field(examples=["Speedrun any%"])
    last_game: str | None = Field(examples=["Celeste"])
    is_live: bool
    live_stream_id: int | None


class MessageResult(BaseModel):
    message_id: UUID
    stream_id: int
    author_name: str = Field(examples=["Célèste"])
    content: str = Field(examples=["GG WP !"])
    sent_at: datetime


class SearchResults(BaseModel):
    streamers: list[StreamerResult]
    messages: list[MessageResult]

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Mp4Status = Literal["none", "processing", "ready", "failed"]


class ReplayResponse(BaseModel):
    stream_id: int
    streamer_id: int
    streamer_name: str | None = Field(examples=["Célèste"])
    title: str | None = Field(examples=["Speedrun any%"])
    game: str | None = Field(examples=["Celeste"])
    started_at: datetime | None
    ended_at: datetime
    duration_s: float = Field(examples=[3725.4])
    mp4_status: Mp4Status
    playback_url: str = Field(examples=["/replays/7/video"])


class ReplayPage(BaseModel):
    items: list[ReplayResponse]
    total: int
    page: int
    size: int


class ConversionPending(BaseModel):
    stream_id: int
    mp4_status: Literal["processing"] = "processing"

from pydantic import BaseModel, Field


class StreamerResult(BaseModel):
    streamer_id: int
    streamer_name: str = Field(examples=["Célèste"])
    last_title: str | None = Field(examples=["Speedrun any%"])
    last_game: str | None = Field(examples=["Celeste"])
    is_live: bool
    live_stream_id: int | None


class StreamerPage(BaseModel):
    items: list[StreamerResult]
    total: int
    page: int
    size: int

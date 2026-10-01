from pydantic import BaseModel


class StreamerResult(BaseModel):
    streamer_id: str
    streamer_name: str
    last_title: str | None
    last_game: str | None
    is_live: bool
    live_stream_id: str | None

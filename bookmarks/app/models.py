from datetime import datetime
from enum import Enum
from pydantic import BaseModel


class TargetType(str, Enum):
    REPLAY = "replay"
    STREAMER = "streamer"


class BookmarkCreate(BaseModel):
    target_type: TargetType
    target_id: int
    label: str
    note: str | None = None


class BookmarkUpdate(BaseModel):
    label: str | None = None
    note: str | None = None


class BookmarkResponse(BaseModel):
    id: int
    user_id: int
    target_type: TargetType
    target_id: int
    label: str
    note: str | None = None
    created_at: datetime
    updated_at: datetime
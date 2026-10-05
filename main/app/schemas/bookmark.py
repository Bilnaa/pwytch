from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

MAX_POSTGRES_INTEGER = 2_147_483_647


class TargetType(StrEnum):
    REPLAY = "replay"
    STREAMER = "streamer"


class BookmarkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_type: TargetType
    target_id: int = Field(gt=0, le=MAX_POSTGRES_INTEGER, strict=True)
    label: str = Field(examples=["Run record"])
    note: str | None = Field(default=None, examples=["Le skip du chapitre 3"])


class BookmarkUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(default=None, examples=["Run record"])
    note: str | None = Field(default=None, examples=["Le skip du chapitre 3"])


class BookmarkResponse(BaseModel):
    id: int
    user_id: int
    target_type: TargetType
    target_id: int
    label: str
    note: str | None
    created_at: datetime
    updated_at: datetime

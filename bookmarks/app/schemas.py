from datetime import datetime
from enum import Enum
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, StringConstraints


MAX_TARGET_ID = 2**31 - 1


Note = Annotated[
    str | None,
    StringConstraints(strip_whitespace=True),
    Field(
        description="Optional note for the bookmark",
        max_length=300,
        min_length=1
    )
]


Label = Annotated[
    str,
    StringConstraints(strip_whitespace=True),
    Field(
        description="Label for the bookmark",
        max_length=100,
        min_length=1
    )
]


class TargetType(str, Enum):
    REPLAY = "replay"
    STREAMER = "streamer"


class BookmarkCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    target_type: TargetType
    target_id: int = Field(description="ID of the target to bookmark", gt=0, le=MAX_TARGET_ID)
    label: Label
    note: Note | None = None


class BookmarkUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    label: Label = None
    note: Note | None = None


class BookmarkResponse(BaseModel):
    id: int
    user_id: int
    target_type: TargetType
    target_id: int
    label: str
    note: str | None = None
    created_at: datetime
    updated_at: datetime
from datetime import datetime
from enum import Enum
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from app.utils import LIMIT_INTEGER


def reject_null_characters(value: str) -> str:
    if "\u0000" in value:
        raise ValueError("Null character is not allowed")
    return value


Note = Annotated[
    str | None,
    StringConstraints(strip_whitespace=True),
    Field(
        description="Optional note for the bookmark",
        max_length=300,
        min_length=1
    ),
    AfterValidator(reject_null_characters),
]


Label = Annotated[
    str,
    StringConstraints(strip_whitespace=True),
    Field(
        description="Label for the bookmark",
        max_length=100,
        min_length=1
    ),
    AfterValidator(reject_null_characters),
]


class TargetType(str, Enum):
    REPLAY = "replay"
    STREAMER = "streamer"


class BookmarkCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    target_type: TargetType
    target_id: int = Field(description="ID of the target to bookmark", gt=0, le=LIMIT_INTEGER, strict=True)
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
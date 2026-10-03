from datetime import datetime
from enum import Enum
from typing import Annotated
from pydantic import AfterValidator, BaseModel, ConfigDict

def reject_none(value: str | None) -> str:
    if value is None:
        raise ValueError("Value cannot be None")
    return value

class TargetType(str, Enum):
    REPLAY = "replay"
    STREAMER = "streamer"


class BookmarkCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    
    target_type: TargetType
    target_id: int
    label: str
    note: str | None = None


class BookmarkUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    label: Annotated[str | None, AfterValidator(reject_none)] = None
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
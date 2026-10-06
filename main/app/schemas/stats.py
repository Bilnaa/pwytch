from common.events import ItemType, TargetType
from pydantic import BaseModel, Field


class CounterResponse(BaseModel):
    item_type: ItemType
    item_id: str = Field(examples=["42"])
    count: int


class BookmarkDeletedCounterResponse(BaseModel):
    target_type: TargetType
    target_id: int = Field(examples=[7])
    count: int


class ChatMessageCounterResponse(BaseModel):
    stream_id: int = Field(examples=[12])
    count: int


class PlayerEventCountersResponse(BaseModel):
    stream_id: int = Field(examples=[12])
    play: int
    pause: int
    stop: int

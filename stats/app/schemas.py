from common.events import ItemType, TargetType
from pydantic import BaseModel


class SearchCountResponse(BaseModel):
    item_type: ItemType
    item_id: str
    count: int


class BookmarkDeletedCountResponse(BaseModel):
    target_type: TargetType
    target_id: int
    count: int


class ChatMessageCountResponse(BaseModel):
    stream_id: int
    count: int
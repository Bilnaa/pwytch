from common.events import ItemType
from pydantic import BaseModel, Field


class CounterResponse(BaseModel):
    item_type: ItemType
    item_id: str = Field(examples=["42"])
    count: int

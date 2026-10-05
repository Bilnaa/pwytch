from common.events import ItemType
from pydantic import BaseModel


class CounterResponse(BaseModel):
    item_type: ItemType
    item_id: str
    count: int

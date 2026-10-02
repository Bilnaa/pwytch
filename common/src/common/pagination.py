from pydantic import BaseModel


class Page[ItemType](BaseModel):
    items: list[ItemType]
    total: int
    page: int
    size: int

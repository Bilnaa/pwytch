from pydantic import BaseModel


class Stats(BaseModel):
    counter_type: str
    key: str
    value: int

from datetime import datetime, UTC
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

class Author(BaseModel):
    id : int
    username : str

class MessageModel(BaseModel):
    id : UUID = Field(default_factory=uuid4)
    stream_id : int
    author : Author
    content: str
    sent_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
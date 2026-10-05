from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ChatAuthor(BaseModel):
    id: int
    username: str = Field(examples=["Célèste"])


class ChatMessage(BaseModel):
    id: UUID
    stream_id: int
    author: ChatAuthor
    content: str = Field(examples=["GG WP !"])
    sent_at: datetime

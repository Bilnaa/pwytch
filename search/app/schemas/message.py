from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class MessageResult(BaseModel):
    message_id: UUID
    stream_id: int
    author_name: str
    content: str
    sent_at: datetime

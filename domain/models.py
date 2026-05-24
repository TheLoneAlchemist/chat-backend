from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime
from uuid import UUID

class User(BaseModel):
    id: str
    username: str
    avatar_url: Optional[str] = None
    is_anonymous: bool = True

class MessagePayload(BaseModel):
    room: str = "global"
    content: str = Field(..., min_length=1, max_length=2000)
    parent_id: Optional[str] = None   # reply to
    quote_id: Optional[str] = None   # quote reference

class EditPayload(BaseModel):
    message_id: str
    content: str = Field(..., min_length=1, max_length=2000)

class DeletePayload(BaseModel):
    message_id: str

class TypingPayload(BaseModel):
    room: str
    typing: bool = True

class ReadPayload(BaseModel):
    message_id: str

# WebSocket protocol envelope
class WsMessage(BaseModel):
    t: Literal["join","msg","edit","del","type","read","ping","upgrade"]
    d: dict
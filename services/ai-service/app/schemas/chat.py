from pydantic import BaseModel
from typing import Optional


class ChatRequest(BaseModel):
    user_id: str
    message: str
    session_id: str
    telegram_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    session_id: str

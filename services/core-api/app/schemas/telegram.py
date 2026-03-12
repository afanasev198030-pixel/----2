from pydantic import BaseModel
from typing import Dict, Any, Optional

class TelegramLinkRequest(BaseModel):
    token: str
    telegram_id: str

class TelegramLinkResponse(BaseModel):
    status: str
    message: str
    user_id: str

class TelegramLogRequest(BaseModel):
    user_id: str
    action: str
    details: Optional[Dict[str, Any]] = None

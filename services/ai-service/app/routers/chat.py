import json
import structlog
from fastapi import APIRouter, Depends, HTTPException
import redis.asyncio as redis

from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_agent import AdvancedConversationalAgent
from app.config import get_settings

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/ai/chat", tags=["chat"])

redis_client = redis.from_url(get_settings().REDIS_BROKER_URL, decode_responses=True)
agent = AdvancedConversationalAgent()

@router.post("", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    session_key = f"chat_session:{request.session_id}"
    
    # Load history
    history_str = await redis_client.get(session_key)
    history = json.loads(history_str) if history_str else []
    
    # Process message
    response_text = await agent.process_message(
        user_id=request.user_id,
        message=request.message,
        history=history
    )
    
    # Update history
    history.append({"role": "user", "content": request.message})
    history.append({"role": "assistant", "content": response_text})
    
    # Keep only last 10 messages to save context window
    if len(history) > 10:
        history = history[-10:]
        
    # Save history (expire in 1 hour)
    await redis_client.setex(session_key, 3600, json.dumps(history))
    
    return ChatResponse(
        response=response_text,
        session_id=request.session_id
    )

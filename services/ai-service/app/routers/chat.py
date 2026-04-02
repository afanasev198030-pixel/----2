import json
import structlog
from fastapi import APIRouter
import redis.asyncio as redis

from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_agent import ReActAgent
from app.config import get_settings

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/ai/chat", tags=["chat"])

redis_client = redis.from_url(get_settings().REDIS_BROKER_URL, decode_responses=True)
agent = ReActAgent()

SESSION_MAX_RAW = 16
SESSION_KEEP_RECENT = 6
SESSION_TTL = 3600


@router.post("", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    session_key = f"chat_session:{request.session_id}"

    history_str = await redis_client.get(session_key)
    history = json.loads(history_str) if history_str else []

    response_text = await agent.process_message(
        user_id=request.user_id,
        message=request.message,
        history=history,
        telegram_id=request.telegram_id,
    )

    history.append({"role": "user", "content": request.message})
    history.append({"role": "assistant", "content": response_text})

    if len(history) > SESSION_MAX_RAW:
        try:
            old_part = history[:-SESSION_KEEP_RECENT]
            summary = await agent.summarize_history(old_part)
            if summary:
                history = [
                    {"role": "system", "content": f"Краткое резюме предыдущего диалога: {summary}"}
                ] + history[-SESSION_KEEP_RECENT:]
                logger.info("session_compacted", session=request.session_id, old_len=len(old_part))
        except Exception as e:
            logger.warning("session_compact_failed", error=str(e))
            history = history[-SESSION_MAX_RAW:]

    await redis_client.setex(session_key, SESSION_TTL, json.dumps(history))

    return ChatResponse(
        response=response_text,
        session_id=request.session_id,
    )

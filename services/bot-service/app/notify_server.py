"""
Lightweight FastAPI server inside bot-service for receiving push notifications
from core-api (declaration status changes, parsing complete, etc.).
Runs alongside aiogram polling on port 8006.
"""

import structlog
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict, Any, Optional
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

logger = structlog.get_logger()

app = FastAPI(title="bot-service-notify", docs_url=None, redoc_url=None)

_bot: Optional[Bot] = None

WEB_BASE_URL = "http://141.105.65.148"


def set_bot(bot: Bot):
    global _bot
    _bot = bot


class NotifyRequest(BaseModel):
    telegram_id: str
    event: str
    data: Dict[str, Any] = {}


EVENT_TEMPLATES = {
    "parsing_complete": (
        "✅ Декларация ...{short_id} заполнена AI.\n"
        "📦 Товарных позиций: {items_count}\n"
        "Проверьте и подтвердите."
    ),
    "requires_attention": (
        "⚠️ Декларация ...{short_id} требует внимания.\n"
        "Блокирующих проблем: {blocking_count}\n"
        "Откройте для исправления."
    ),
    "ready_to_send": (
        "🎉 Декларация ...{short_id} готова к отправке!\n"
        "Подпишите и отправьте."
    ),
    "sent": "📨 Декларация ...{short_id} успешно отправлена!",
    "status_changed": (
        "📋 Статус декларации ...{short_id} изменён:\n"
        "{old} → {new}"
    ),
}


def _format_notification(event: str, data: Dict[str, Any]) -> str:
    decl_id = data.get("declaration_id", "")
    short_id = decl_id[-8:] if decl_id else "?"

    template = EVENT_TEMPLATES.get(event)
    if not template:
        return f"🔔 Событие: {event}\n{data}"

    return template.format(
        short_id=short_id,
        items_count=data.get("items_count", "?"),
        blocking_count=data.get("blocking_count", "?"),
        old=data.get("old", "?"),
        new=data.get("new", "?"),
    )


def _build_keyboard(event: str, data: Dict[str, Any]) -> Optional[InlineKeyboardMarkup]:
    decl_id = data.get("declaration_id", "")
    if not decl_id:
        return None

    buttons = []

    if event == "ready_to_send":
        buttons.append([
            InlineKeyboardButton(text="✍️ Подписать", callback_data=f"decl_sign:{decl_id}"),
            InlineKeyboardButton(text="🔍 Проверить", callback_data=f"decl_presend:{decl_id}"),
        ])
        buttons.append([
            InlineKeyboardButton(text="🌐 Открыть форму", url=f"{WEB_BASE_URL}/declarations/{decl_id}/form"),
        ])
    elif event == "requires_attention":
        buttons.append([
            InlineKeyboardButton(text="🔍 Показать проблемы", callback_data=f"decl_presend:{decl_id}"),
            InlineKeyboardButton(text="🌐 Открыть", url=f"{WEB_BASE_URL}/declarations/{decl_id}/form"),
        ])
    elif event in ("parsing_complete", "status_changed"):
        buttons.append([
            InlineKeyboardButton(text="📋 Статус", callback_data=f"decl_status:{decl_id}"),
            InlineKeyboardButton(text="🌐 Открыть", url=f"{WEB_BASE_URL}/declarations/{decl_id}/form"),
        ])
    else:
        buttons.append([
            InlineKeyboardButton(text="🌐 Открыть", url=f"{WEB_BASE_URL}/declarations/{decl_id}/form"),
        ])

    return InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None


@app.post("/notify")
async def notify_user(req: NotifyRequest):
    if not _bot:
        logger.error("notify_bot_not_set")
        return {"status": "error", "detail": "bot not initialized"}

    text = _format_notification(req.event, req.data)
    keyboard = _build_keyboard(req.event, req.data)

    try:
        await _bot.send_message(
            chat_id=int(req.telegram_id),
            text=text,
            reply_markup=keyboard,
        )
        logger.info("push_notification_sent", telegram_id=req.telegram_id, event=req.event)
        return {"status": "ok"}
    except Exception as e:
        logger.error("push_notification_failed", telegram_id=req.telegram_id, error=str(e))
        return {"status": "error", "detail": str(e)}


@app.get("/health")
async def health():
    return {"status": "ok", "bot_ready": _bot is not None}

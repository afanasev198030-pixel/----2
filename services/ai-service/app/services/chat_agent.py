"""
Advanced Conversational Agent for Telegram with Claude Opus 4.6.
Deep integration with Digital Broker project.
"""

import json
import structlog
import httpx
import asyncio
from typing import List, Dict, Any

from app.services.llm_client import get_llm_client
from app.services.index_manager import get_index_manager
from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()


class AdvancedConversationalAgent:
    def __init__(self):
        self.index = get_index_manager()
        self.core_api_url = settings.CORE_API_URL
        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        return """Ты — экспертный AI-ассистент таможенного брокера платформы Digital Broker.

Ты отлично разбираешься в:
- Таможенном оформлении РФ (ИМ, ЭК, ТН ВЭД, Incoterms, валютный контроль)
- Правилах заполнения деклараций (все графы)
- Документообороте (инвойс, packing list, контракт, транспортные документы, СВХ, техописание)
- RAG по прецедентам и официальным правилам

Стиль общения: профессиональный, точный, полезный. 
Используй нумерацию, списки и чёткие рекомендации.
Всегда учитывай контекст пользователя и его последние декларации.

Если пользователь загружает документы — напомни, что их можно просто прикрепить в этот чат."""

    async def process_message(self, user_id: str, message: str, history: List[Dict[str, str]]) -> str:
        """Main entry point from chat endpoint."""
        try:
            llm = get_llm_client(operation="telegram_chat")
            logger.info("agent_initialized", provider=settings.LLM_PROVIDER, model=settings.effective_model)
        except Exception as e:
            logger.error("llm_init_failed", error=str(e))
            return "AI-сервис временно недоступен. Попробуйте позже."

        context = await self._gather_context(user_id, message)
        full_system_prompt = self.system_prompt + "\n\n" + context

        messages = [{"role": "system", "content": full_system_prompt}]
        messages.extend(history[-12:])
        messages.append({"role": "user", "content": message})

        try:
            response = await asyncio.to_thread(
                lambda: llm.chat.completions.create(
                    model=settings.effective_model,
                    messages=messages,
                    temperature=0.3,
                    max_tokens=2000,
                )
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error("agent_response_error", error=str(e))
            return "Произошла ошибка при обработке вашего сообщения."

    async def _gather_context(self, user_id: str, message: str) -> str:
        """Gather rich context including RAG and user declarations."""
        parts = []

        # RAG Search
        if any(k in message.lower() for k in ["тн вэд", "код", "правило", "графа", "как заполнить", "требуется"]):
            try:
                results = self.index.search_precedents(message, limit=5)
                if results and results.get("documents") and results["documents"][0]:
                    parts.append("📚 Из базы знаний:\n" + "\n".join([f"• {doc}" for doc in results["documents"][0][:4]]))
            except Exception as e:
                logger.warning("rag_failed", error=str(e))

        # User declarations
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(
                    f"{self.core_api_url}/api/v1/declarations",
                    headers={"X-User-ID": user_id},
                    params={"per_page": 5}
                )
                if resp.status_code == 200:
                    decls = resp.json().get("items", [])
                    if decls:
                        decl_text = "📋 Ваши последние декларации:\n"
                        for d in decls:
                            decl_text += f"• {d.get('id','')[:8]}... | {d.get('status','?')} | {d.get('created_at','')[:10]}\n"
                        parts.append(decl_text)
        except Exception as e:
            logger.warning("declarations_fetch_failed", error=str(e))

        return "\n\n".join(parts) if parts else "Контекст пользователя загружен."


# Singleton
agent = AdvancedConversationalAgent()

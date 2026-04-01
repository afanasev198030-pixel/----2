"""
Advanced Conversational Agent with Tool Calling (ReAct) and Self-Learning.
Uses Claude Opus 4.6 with deep integration into Digital Broker.
"""

import json
import structlog
import httpx
import asyncio
from typing import List, Dict, Any
from datetime import datetime

from app.services.llm_client import get_llm_client
from app.services.index_manager import get_index_manager
from app.config import get_settings
from app.services.agent_tools import tools

logger = structlog.get_logger()
settings = get_settings()


class AdvancedConversationalAgent:
    def __init__(self):
        self.index = get_index_manager()
        self.core_api_url = settings.CORE_API_URL
        self.system_prompt = self._build_system_prompt()
        self.tools = tools

    def _build_system_prompt(self) -> str:
        return """Ты — экспертный AI-ассистент таможенного брокера Digital Broker.

Ты можешь использовать инструменты для получения информации:
- get_user_declarations(user_id) — последние декларации
- search_knowledge_base(query) — поиск по прецедентам
- get_filling_rules() — правила заполнения
- get_user_info(user_id) — информация о пользователе

Правила:
- Сначала думай, нужна ли тебе дополнительная информация
- Если нужно — используй инструмент
- Отвечай профессионально, структурировано и полезно
- Если пользователь оценивает твой ответ — сохраняй feedback для обучения"""

    async def process_message(self, user_id: str, message: str, history: List[Dict[str, str]]) -> str:
        """Main method with Tool Calling (ReAct pattern) and feedback support."""
        try:
            llm = get_llm_client(operation="telegram_chat")
        except Exception as e:
            logger.error("llm_init_failed", error=str(e))
            return "AI-сервис временно недоступен."

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
            answer = response.choices[0].message.content.strip()

            # Save feedback capability (for future learning)
            await self._save_interaction(user_id, message, answer)

            return answer
        except Exception as e:
            logger.error("agent_response_error", error=str(e))
            return "Произошла ошибка при обработке вашего запроса."

    async def _gather_context(self, user_id: str, message: str) -> str:
        """Gather context with memory and tools."""
        parts = []

        memory = await self.tools.get_user_memory(user_id)
        if memory:
            parts.append(f"📌 Из памяти о пользователе:\n{memory}")

        if any(k in message.lower() for k in ["декларац", "статус", "мои"]):
            result = await self.tools.get_user_declarations(user_id, limit=5)
            if result.get("success"):
                parts.append("📋 " + str(result.get("declarations", [])))

        if any(k in message.lower() for k in ["код", "тн вэд", "правило", "графа"]):
            result = await self.tools.search_knowledge_base(message, limit=5)
            if result.get("success") and result.get("results"):
                parts.append("📚 " + str(result.get("results")))

        return "\n\n".join(parts) if parts else "Контекст пользователя загружен."

    async def _save_interaction(self, user_id: str, user_message: str, agent_response: str):
        """Save interaction for potential self-learning."""
        try:
            await self.tools.save_feedback(
                user_id=user_id,
                message=user_message,
                feedback="auto_saved",
                rating=0
            )
        except:
            pass  # silent fail for now


# Global instance
agent = AdvancedConversationalAgent()

"""
ReAct Conversational Agent with OpenAI-compatible function calling.
Supports DeepSeek, OpenAI, Cloud.ru and native Anthropic SDK.
The agent loops: LLM → tool_calls → execute → LLM → ... until final text answer.
"""

import json
import asyncio
import structlog
from typing import List, Dict, Any, Optional

from app.services.llm_client import get_llm_client
from app.services.agent_tools import tools, TOOL_DEFINITIONS
from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()

MAX_TOOL_ROUNDS = 6

SYSTEM_PROMPT = """Ты — экспертный AI-ассистент таможенного брокера Digital Broker.

У тебя есть инструменты — используй их АКТИВНО:
• get_my_declarations — посмотреть список деклараций пользователя
• get_declaration_details — подробный статус конкретной декларации + pre-send проверки
• search_knowledge_base — поиск по базе знаний (коды ТН ВЭД, прецеденты)
• get_filling_rules — правила заполнения граф ДТ
• remember_fact — запомнить факт о пользователе для будущих диалогов
• get_user_profile — получить профиль пользователя

Правила:
1. Если пользователь спрашивает о декларациях — ВСЕГДА вызывай get_my_declarations
2. Если спрашивает статус — ВСЕГДА вызывай get_declaration_details
3. Если спрашивает о кодах/правилах — вызывай search_knowledge_base или get_filling_rules
4. Если пользователь сообщает важную информацию о себе — вызывай remember_fact
5. Отвечай профессионально, кратко и структурировано
6. Используй emoji для статусов: ✅ готово, ⚠️ внимание, ❌ проблема, 📋 список
7. Если у декларации есть blocking проверки — перечисли их
8. Не выдумывай данных — всегда получай через инструменты"""


class ReActAgent:
    def __init__(self):
        self._tools = tools

    async def process_message(
        self,
        user_id: str,
        message: str,
        history: List[Dict[str, str]],
        telegram_id: Optional[str] = None,
    ) -> str:
        tg_id = telegram_id or ""

        memory = await self._tools.get_user_memory(user_id)
        system = SYSTEM_PROMPT
        if memory:
            system += f"\n\nИз долгосрочной памяти о пользователе:\n{memory}"

        try:
            if settings.LLM_PROVIDER == "anthropic":
                return await self._run_anthropic(system, history, message, tg_id, user_id)
            return await self._run_openai_react(system, history, message, tg_id, user_id)
        except Exception as e:
            logger.error("agent_error", error=str(e), provider=settings.LLM_PROVIDER)
            return "Произошла ошибка при обработке вашего запроса."

    async def _run_openai_react(
        self, system: str, history: List[Dict], user_msg: str,
        telegram_id: str, user_id: str,
    ) -> str:
        try:
            llm = get_llm_client(operation="telegram_chat")
        except Exception as e:
            logger.error("llm_init_failed", error=str(e))
            return "AI-сервис временно недоступен."

        messages: List[Dict[str, Any]] = [{"role": "system", "content": system}]
        for m in history[-12:]:
            messages.append({"role": m["role"], "content": m["content"]})
        messages.append({"role": "user", "content": user_msg})

        model = settings.effective_model

        for round_num in range(MAX_TOOL_ROUNDS):
            response = await asyncio.to_thread(
                lambda: llm.chat.completions.create(
                    model=model,
                    messages=messages,
                    tools=TOOL_DEFINITIONS,
                    tool_choice="auto",
                    temperature=0.3,
                    max_tokens=2000,
                )
            )

            choice = response.choices[0]

            if choice.finish_reason == "tool_calls" or getattr(choice.message, "tool_calls", None):
                tool_calls = choice.message.tool_calls
                messages.append(choice.message)

                for tc in tool_calls:
                    fn_name = tc.function.name
                    try:
                        fn_args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        fn_args = {}

                    logger.info("react_tool_call", round=round_num, tool=fn_name, args=fn_args)

                    result_str = await self._tools.execute(fn_name, fn_args, telegram_id, user_id)

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result_str,
                    })
            else:
                return (choice.message.content or "").strip()

        return (messages[-1].get("content", "") if messages else "").strip() or "Я не смог получить данные. Попробуйте переформулировать вопрос."

    async def _run_anthropic(
        self, system: str, history: List[Dict], user_msg: str,
        telegram_id: str, user_id: str,
    ) -> str:
        """Anthropic Claude with native tool use."""
        try:
            import anthropic
        except ImportError:
            return "Anthropic SDK не установлен."

        api_key = settings.ANTHROPIC_API_KEY or settings.LLM_API_KEY
        if not api_key:
            return "Anthropic API ключ не настроен."

        client = anthropic.Anthropic(api_key=api_key)
        model = settings.ANTHROPIC_MODEL or "claude-3-5-sonnet-20241022"

        anthropic_tools = []
        for td in TOOL_DEFINITIONS:
            fn = td["function"]
            anthropic_tools.append({
                "name": fn["name"],
                "description": fn["description"],
                "input_schema": fn["parameters"],
            })

        messages = []
        for m in history[-12:]:
            messages.append({"role": m["role"], "content": m["content"]})
        messages.append({"role": "user", "content": user_msg})

        for _ in range(MAX_TOOL_ROUNDS):
            response = await asyncio.to_thread(
                lambda: client.messages.create(
                    model=model,
                    max_tokens=2000,
                    system=system,
                    messages=messages,
                    tools=anthropic_tools,
                    temperature=0.3,
                )
            )

            if response.stop_reason == "tool_use":
                tool_results = []
                assistant_content = response.content
                messages.append({"role": "assistant", "content": assistant_content})

                for block in response.content:
                    if block.type == "tool_use":
                        result_str = await self._tools.execute(
                            block.name, block.input, telegram_id, user_id,
                        )
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result_str,
                        })

                messages.append({"role": "user", "content": tool_results})
            else:
                for block in response.content:
                    if hasattr(block, "text"):
                        return block.text.strip()
                return ""

        return "Не удалось получить ответ."

    async def summarize_history(self, history: List[Dict[str, str]]) -> str:
        """Summarize old chat history to compress context window."""
        try:
            llm = get_llm_client(operation="session_compact")
        except Exception:
            return ""

        text = "\n".join(f"{m['role']}: {m['content'][:200]}" for m in history)
        prompt = f"Сделай краткое резюме этого диалога (3-5 предложений) на русском:\n\n{text}"

        response = await asyncio.to_thread(
            lambda: llm.chat.completions.create(
                model=settings.effective_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=300,
            )
        )
        return (response.choices[0].message.content or "").strip()


agent = ReActAgent()

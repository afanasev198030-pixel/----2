"""
Agent Tools for ReAct conversational agent.
Each tool is registered as an OpenAI function calling schema
and has a corresponding async executor method.
"""

import json
import structlog
import httpx
from typing import Dict, Any, List, Optional

from app.config import get_settings
import redis.asyncio as redis

logger = structlog.get_logger()

TOOL_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_my_declarations",
            "description": "Получить список последних деклараций пользователя. Вызывай, когда пользователь спрашивает про свои декларации, статусы, или просит показать список.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Максимальное количество деклараций (по умолчанию 5)",
                        "default": 5,
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_declaration_details",
            "description": "Получить подробный статус декларации, включая pre-send проверки и количество товаров/документов. Вызывай при вопросе о конкретной декларации.",
            "parameters": {
                "type": "object",
                "properties": {
                    "declaration_id": {
                        "type": "string",
                        "description": "UUID декларации",
                    }
                },
                "required": ["declaration_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_knowledge_base",
            "description": "Поиск по базе знаний (прецеденты, правила ТН ВЭД, коды). Вызывай при вопросах о кодах, правилах заполнения, графах ДТ.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Поисковый запрос",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_filling_rules",
            "description": "Получить правила заполнения деклараций. Вызывай при вопросах 'как заполнить графу X', 'какие правила'.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remember_fact",
            "description": "Запомнить важный факт о пользователе для будущих диалогов (ИНН, основные товары, предпочтения, частые маршруты).",
            "parameters": {
                "type": "object",
                "properties": {
                    "fact": {
                        "type": "string",
                        "description": "Факт для запоминания",
                    }
                },
                "required": ["fact"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_user_profile",
            "description": "Получить профиль пользователя (имя, email, компания, роль).",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]


class AgentTools:
    """Executes tools on behalf of the agent. All methods use internal telegram API (no JWT)."""

    def __init__(self):
        self._redis: Optional[redis.Redis] = None

    @property
    def core_api_url(self) -> str:
        return get_settings().CORE_API_URL

    async def _get_redis(self) -> redis.Redis:
        if self._redis is None:
            self._redis = redis.from_url(get_settings().REDIS_BROKER_URL, decode_responses=True)
        return self._redis

    async def execute(self, tool_name: str, arguments: Dict[str, Any], telegram_id: str, user_id: str) -> str:
        """Dispatch tool call and return JSON-serialised result string."""
        logger.info("tool_execute", tool=tool_name, telegram_id=telegram_id)
        try:
            if tool_name == "get_my_declarations":
                result = await self.get_my_declarations(telegram_id, arguments.get("limit", 5))
            elif tool_name == "get_declaration_details":
                result = await self.get_declaration_details(telegram_id, arguments["declaration_id"])
            elif tool_name == "search_knowledge_base":
                result = await self.search_knowledge_base(arguments["query"])
            elif tool_name == "get_filling_rules":
                result = await self.get_filling_rules()
            elif tool_name == "remember_fact":
                result = await self.remember_fact(user_id, arguments["fact"])
            elif tool_name == "get_user_profile":
                result = await self.get_user_profile(telegram_id)
            else:
                result = {"error": f"Unknown tool: {tool_name}"}
            return json.dumps(result, ensure_ascii=False, default=str)
        except Exception as e:
            logger.error("tool_execute_error", tool=tool_name, error=str(e))
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    async def get_my_declarations(self, telegram_id: str, limit: int = 5) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self.core_api_url}/api/v1/telegram/user/{telegram_id}/declarations",
                params={"limit": limit},
            )
            if resp.status_code == 200:
                return resp.json()
            return {"error": f"HTTP {resp.status_code}: {resp.text[:200]}"}

    async def get_declaration_details(self, telegram_id: str, declaration_id: str) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self.core_api_url}/api/v1/telegram/user/{telegram_id}/declaration/{declaration_id}/status",
            )
            if resp.status_code == 200:
                return resp.json()
            return {"error": f"HTTP {resp.status_code}: {resp.text[:200]}"}

    async def search_knowledge_base(self, query: str, limit: int = 5) -> Dict[str, Any]:
        try:
            from app.services.index_manager import get_index_manager
            index = get_index_manager()
            results = index.search_precedents(query, top_k=limit)
            if results:
                return {"results": [r.get("text", "")[:500] for r in results[:limit]], "query": query}
            return {"results": [], "query": query}
        except Exception as e:
            logger.error("tool_search_kb_failed", query=query, error=str(e))
            return {"error": str(e)}

    async def get_filling_rules(self) -> Dict[str, Any]:
        try:
            from app.services.rules_engine import get_filling_rules_text
            rules_text = get_filling_rules_text()
            return {"rules": rules_text[:2000] if rules_text else "Правила не загружены"}
        except Exception as e:
            return {"error": str(e)}

    async def remember_fact(self, user_id: str, fact: str) -> Dict[str, Any]:
        r = await self._get_redis()
        key = f"user_memory:{user_id}"
        current = await r.get(key) or ""
        updated = f"{current}\n{fact}".strip() if current else fact
        await r.setex(key, 60 * 60 * 24 * 90, updated)
        return {"saved": True, "fact": fact}

    async def get_user_profile(self, telegram_id: str) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self.core_api_url}/api/v1/telegram/user/{telegram_id}/profile",
            )
            if resp.status_code == 200:
                return resp.json()
            return {"error": f"HTTP {resp.status_code}: {resp.text[:200]}"}

    async def get_user_memory(self, user_id: str) -> str:
        try:
            r = await self._get_redis()
            return await r.get(f"user_memory:{user_id}") or ""
        except Exception:
            return ""


tools = AgentTools()

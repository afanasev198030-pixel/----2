"""
Agent Tools for AdvancedConversationalAgent.
Provides structured tools that the agent can call to interact with the Digital Broker system.
"""

import structlog
import httpx
import json
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.config import get_settings
import redis.asyncio as redis

logger = structlog.get_logger()
settings = get_settings()


class AgentTools:
    """Collection of tools available to the AI agent."""

    def __init__(self):
        self.core_api_url = settings.CORE_API_URL
        self.redis = redis.from_url(settings.REDIS_BROKER_URL, decode_responses=True)

    # ==================== CORE TOOLS ====================

    async def get_user_declarations(self, user_id: str, limit: int = 5) -> Dict[str, Any]:
        """Get recent declarations for a user."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.core_api_url}/api/v1/declarations",
                    headers={"X-User-ID": user_id},
                    params={"per_page": limit}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return {
                        "success": True,
                        "declarations": data.get("items", []),
                        "total": data.get("total", 0)
                    }
                return {"success": False, "error": f"HTTP {resp.status_code}"}
        except Exception as e:
            logger.error("tool_get_declarations_failed", user_id=user_id, error=str(e))
            return {"success": False, "error": str(e)}

    async def search_knowledge_base(self, query: str, limit: int = 5) -> Dict[str, Any]:
        """Search knowledge base using RAG."""
        try:
            from app.services.index_manager import get_index_manager
            index = get_index_manager()
            results = index.search_precedents(query, top_k=limit)

            if results:
                return {
                    "success": True,
                    "results": [r.get("text", "") for r in results[:limit]],
                    "query": query
                }
            return {"success": True, "results": [], "query": query}
        except Exception as e:
            logger.error("tool_search_kb_failed", query=query, error=str(e))
            return {"success": False, "error": str(e)}

    async def get_filling_rules(self, section: str = "all") -> Dict[str, Any]:
        """Get filling rules for declarations."""
        try:
            from app.services.rules_engine import get_filling_rules_text
            rules_text = get_filling_rules_text()
            return {
                "success": True,
                "rules": rules_text[:1500] if rules_text else "Rules not available",
                "section": section
            }
        except Exception as e:
            logger.error("tool_get_rules_failed", error=str(e))
            return {"success": False, "error": str(e)}

    async def get_user_info(self, user_id: str) -> Dict[str, Any]:
        """Get user profile from core-api."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.core_api_url}/api/v1/users/{user_id}",
                )
                if resp.status_code == 200:
                    return {"success": True, "user": resp.json()}
                return {"success": False, "error": f"HTTP {resp.status_code}"}
        except Exception as e:
            logger.error("tool_get_user_info_failed", user_id=user_id, error=str(e))
            return {"success": False, "error": str(e)}

    # ==================== MEMORY & FEEDBACK ====================

    async def save_user_memory(self, user_id: str, fact: str) -> bool:
        """Save important fact about user to long-term memory."""
        try:
            key = f"user_memory:{user_id}"
            current = await self.redis.get(key) or ""
            if current:
                current += f"\n{fact}"
            else:
                current = fact
            await self.redis.setex(key, 60*60*24*30, current)  # 30 days
            return True
        except Exception as e:
            logger.error("save_memory_failed", user_id=user_id, error=str(e))
            return False

    async def get_user_memory(self, user_id: str) -> str:
        """Get long-term memory for user."""
        try:
            key = f"user_memory:{user_id}"
            memory = await self.redis.get(key)
            return memory or ""
        except Exception as e:
            logger.warning("get_memory_failed", user_id=user_id, error=str(e))
            return ""

    async def save_feedback(self, user_id: str, message: str, feedback: str, rating: int = 0) -> bool:
        """Save user feedback for learning."""
        try:
            key = f"feedback:{user_id}"
            entry = {
                "timestamp": datetime.now().isoformat(),
                "message": message[:200],
                "feedback": feedback,
                "rating": rating
            }
            await self.redis.lpush(key, json.dumps(entry))
            await self.redis.ltrim(key, 0, 49)  # keep last 50 feedbacks
            return True
        except Exception as e:
            logger.error("save_feedback_failed", error=str(e))
            return False


# Global tools instance
tools = AgentTools()

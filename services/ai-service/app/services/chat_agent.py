import json
import structlog
import httpx
from typing import List, Dict, Any

from app.services.llm_client import get_llm_client
from app.services.index_manager import get_index_manager
from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()

class ConversationalAgent:
    def __init__(self):
        self.index = get_index_manager()
        self.core_api_url = settings.CORE_API_URL
        
    async def process_message(self, user_id: str, message: str, history: List[Dict[str, str]]) -> str:
        # Get LLM client dynamically to pick up latest keys from DB
        try:
            llm = get_llm_client()
        except ValueError as e:
            logger.error("llm_not_configured", error=str(e))
            return "Извините, AI-модель пока не настроена. Пожалуйста, обратитесь к администратору."
        # 1. Check if we need to search knowledge base (RAG)
        context = ""
        if any(keyword in message.lower() for keyword in ["тн вэд", "код", "правило", "как", "документ"]):
            try:
                results = self.index.search_precedents(message, limit=3)
                if results and results.get("documents") and results["documents"][0]:
                    context = "Найденная информация в базе знаний:\n"
                    for doc in results["documents"][0]:
                        context += f"- {doc}\n"
            except Exception as e:
                logger.error("rag_search_error", error=str(e))
                
        # 2. Check if user is asking about their declarations
        declarations_context = ""
        if any(keyword in message.lower() for keyword in ["деклараци", "статус", "мои"]):
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        f"{self.core_api_url}/api/v1/declarations",
                        headers={"X-User-ID": user_id},
                        params={"per_page": 5}
                    )
                    if resp.status_code == 200:
                        decls = resp.json().get("items", [])
                        if decls:
                            declarations_context = "Последние декларации пользователя:\n"
                            for d in decls:
                                status = d.get("status", "unknown")
                                created = d.get("created_at", "")[:10]
                                declarations_context += f"- ID: {d['id'][:8]}..., Статус: {status}, Создана: {created}\n"
                        else:
                            declarations_context = "У пользователя пока нет деклараций.\n"
            except Exception as e:
                logger.error("core_api_fetch_error", error=str(e))

        # 3. Build prompt
        system_prompt = f"""Ты — умный AI-ассистент таможенного брокера Digital Broker.
Твоя задача — помогать клиентам с вопросами по таможенному оформлению, подбору кодов ТН ВЭД и статусу их деклараций.
Отвечай вежливо, профессионально и по делу.

{context}
{declarations_context}
"""
        
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": message})
        
        # 4. Call LLM
        try:
            from app.services.llm_client import get_model
            model_name = get_model()
            
            # Use synchronous API for now since TrackedOpenAIClient wraps the sync client
            import asyncio
            def _call_llm():
                return llm.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=1000
                )
            
            response = await asyncio.to_thread(_call_llm)
            return response.choices[0].message.content
        except Exception as e:
            logger.error("llm_chat_error", error=str(e))
            return "Извините, произошла ошибка при обращении к AI-модели. Возможно, неверный ключ API."

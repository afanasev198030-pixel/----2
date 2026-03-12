import httpx
import structlog
from typing import Optional, Dict, Any, List

from app.config import settings

logger = structlog.get_logger()

class CoreApiClient:
    def __init__(self):
        import os
        # Always use the internal docker network name for the bot
        self.base_url = "http://core-api:8001"
        
    async def log_action(self, user_id: str, action: str, details: dict = None) -> bool:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/v1/telegram/log",
                    json={"user_id": user_id, "action": action, "details": details or {}}
                )
                return response.status_code == 200
            except Exception as e:
                logger.error("core_api_log_error", error=str(e))
                return False
        
    async def link_account(self, token: str, telegram_id: str) -> bool:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/v1/telegram/link",
                    json={"token": token, "telegram_id": str(telegram_id)}
                )
                return response.status_code == 200
            except Exception as e:
                logger.error("core_api_link_error", error=str(e))
                return False

    async def get_user(self, telegram_id: str) -> Optional[Dict[str, Any]]:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/api/v1/telegram/user/{telegram_id}"
                )
                if response.status_code == 200:
                    return response.json()
                return None
            except Exception as e:
                logger.error("core_api_get_user_error", error=str(e))
                return None

    async def create_declaration(self, user_id: str, company_id: str) -> Optional[str]:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/v1/declarations",
                    headers={"X-User-ID": user_id},
                    json={"company_id": company_id}
                )
                if response.status_code in (200, 201):
                    return response.json().get("id")
                return None
            except Exception as e:
                logger.error("core_api_create_declaration_error", error=str(e))
                return None

    async def attach_document(self, user_id: str, declaration_id: str, file_id: str, filename: str) -> bool:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/v1/documents",
                    headers={"X-User-ID": user_id},
                    json={
                        "declaration_id": declaration_id,
                        "file_key": file_id,
                        "original_filename": filename,
                        "doc_type": "other",
                        "mime_type": "application/octet-stream",
                        "file_size": 0
                    }
                )
                return response.status_code in (200, 201)
            except Exception as e:
                logger.error("core_api_attach_document_error", error=str(e))
                return False

class FileServiceClient:
    def __init__(self):
        import os
        # Always use the internal docker network name for the bot
        self.base_url = "http://file-service:8002"
        
    async def upload_file(self, file_bytes: bytes, filename: str, content_type: str) -> Optional[str]:
        async with httpx.AsyncClient() as client:
            try:
                files = {'file': (filename, file_bytes, content_type)}
                response = await client.post(
                    f"{self.base_url}/api/v1/files/upload",
                    files=files
                )
                if response.status_code == 200:
                    return response.json().get("file_id")
                return None
            except Exception as e:
                logger.error("file_service_upload_error", error=str(e))
                return None

class AiServiceClient:
    def __init__(self):
        import os
        # Always use the internal docker network name for the bot
        self.base_url = "http://ai-service:8003"
        
    async def parse_smart(self, declaration_id: str, file_ids: List[str]) -> bool:
        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/v1/ai/parse-smart",
                    json={
                        "declaration_id": declaration_id,
                        "file_ids": file_ids
                    }
                )
                return response.status_code == 200
            except Exception as e:
                logger.error("ai_service_parse_error", error=str(e))
                return False

    async def chat(self, user_id: str, message: str, session_id: str) -> str:
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/v1/ai/chat",
                    json={
                        "user_id": user_id,
                        "message": message,
                        "session_id": session_id
                    }
                )
                if response.status_code == 200:
                    return response.json().get("response", "Извините, я не смог сформулировать ответ.")
                return "Произошла ошибка при обращении к AI-сервису."
            except Exception as e:
                logger.error("ai_service_chat_error", error=str(e))
                return "AI-сервис временно недоступен."

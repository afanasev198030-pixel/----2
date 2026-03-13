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
                    f"{self.base_url}/api/v1/telegram/create-declaration",
                    json={"user_id": user_id, "company_id": company_id}
                )
                if response.status_code in (200, 201):
                    return response.json().get("id")
                logger.error("create_declaration_failed", status=response.status_code, body=response.text)
                return None
            except Exception as e:
                logger.error("core_api_create_declaration_error", error=str(e))
                return None

    async def apply_parsed(self, user_id: str, declaration_id: str, parsed_data: dict) -> bool:
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/v1/telegram/apply-parsed",
                    json={
                        "user_id": user_id,
                        "declaration_id": declaration_id,
                        "parsed_data": parsed_data,
                    }
                )
                if response.status_code in (200, 201):
                    return True
                logger.error("apply_parsed_failed", status=response.status_code, body=response.text[:500])
                return False
            except Exception as e:
                logger.error("core_api_apply_parsed_error", error=str(e))
                return False

    async def attach_document(self, user_id: str, declaration_id: str, file_key: str, filename: str) -> bool:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/v1/telegram/attach-document",
                    json={
                        "user_id": user_id,
                        "declaration_id": declaration_id,
                        "file_key": file_key,
                        "original_filename": filename,
                    }
                )
                return response.status_code in (200, 201)
            except Exception as e:
                logger.error("core_api_attach_document_error", error=str(e))
                return False

class FileServiceClient:
    def __init__(self):
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
                    return response.json().get("file_key")
                return None
            except Exception as e:
                logger.error("file_service_upload_error", error=str(e))
                return None

    async def download_file(self, file_key: str) -> Optional[bytes]:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            try:
                response = await client.get(
                    f"{self.base_url}/api/v1/files/download/{file_key}"
                )
                if response.status_code == 200:
                    return response.content
                logger.error("file_download_failed", status=response.status_code, file_key=file_key)
                return None
            except Exception as e:
                logger.error("file_service_download_error", error=str(e), file_key=file_key)
                return None

class AiServiceClient:
    def __init__(self):
        import os
        # Always use the internal docker network name for the bot
        self.base_url = "http://ai-service:8003"
        
    async def parse_smart_batch(
        self,
        declaration_id: str,
        files_data: List[tuple],
    ) -> Optional[Dict[str, Any]]:
        """Send multiple files to parse-smart. Returns parsed data dict or None on failure."""
        async with httpx.AsyncClient(timeout=300.0) as client:
            try:
                multipart_files = [
                    ("files", (fname, fbytes, ctype))
                    for fbytes, fname, ctype in files_data
                ]
                response = await client.post(
                    f"{self.base_url}/api/v1/ai/parse-smart",
                    files=multipart_files,
                    data={"declaration_id": declaration_id},
                )
                if response.status_code == 200:
                    return response.json()
                logger.error("parse_smart_batch_failed", status=response.status_code, body=response.text[:500])
                return None
            except Exception as e:
                logger.error("ai_service_parse_batch_error", error=str(e))
                return None

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

"""
LlamaIndex RAG ядро: индексы ТН ВЭД, правил СУР и прецедентов.
Заменяет самописные vector_store.py, rag_classifier.py, rag_risk.py.
"""
import json
from pathlib import Path
from typing import Optional
import structlog

logger = structlog.get_logger()

# Lazy imports для graceful degradation
_llamaindex_available = False
try:
    from llama_index.core import (
        VectorStoreIndex,
        Document as LIDocument,
        Settings as LISettings,
        StorageContext,
    )
    from llama_index.core.retrievers import VectorIndexRetriever
    from llama_index.core.query_engine import RetrieverQueryEngine
    from llama_index.embeddings.openai import OpenAIEmbedding
    from llama_index.vector_stores.chroma import ChromaVectorStore
    import chromadb
    _llamaindex_available = True
except ImportError:
    logger.warning("llamaindex_not_available", msg="LlamaIndex not installed, RAG disabled")


class IndexManager:
    """Управление LlamaIndex индексами для RAG."""

    def __init__(self, chromadb_url: str, openai_api_key: str, openai_model: str = "gpt-4o"):
        self._chromadb_url = chromadb_url
        self._openai_api_key = openai_api_key
        self._openai_model = openai_model
        self._initialized = False
        self._chromadb_connected = False

        self.hs_codes_index: Optional[VectorStoreIndex] = None
        self.risk_rules_index: Optional[VectorStoreIndex] = None
        self.precedents_index: Optional[VectorStoreIndex] = None

        self.hs_query_engine = None
        self.risk_query_engine = None
        self.precedent_retriever = None

    @property
    def available(self) -> bool:
        return _llamaindex_available and self._initialized

    @property
    def chromadb_connected(self) -> bool:
        return self._chromadb_connected

    def init_indices(self, hs_codes: list[dict] = None, risk_rules: list[dict] = None):
        """Инициализация индексов при старте сервиса."""
        if not _llamaindex_available:
            logger.warning("skip_init_indices", reason="LlamaIndex not available")
            return

        try:
            # Подключение к ChromaDB (проверяем доступность)
            chroma_host = self._chromadb_url.replace("http://", "").split(":")[0]
            chroma_port = int(self._chromadb_url.split(":")[-1])
            chroma_client = chromadb.HttpClient(host=chroma_host, port=chroma_port)

            # Проверка подключения
            chroma_client.heartbeat()
            self._chromadb_connected = True
            logger.info("chromadb_connected", host=chroma_host, port=chroma_port)

            # Если нет OpenAI ключа — не создаём embeddings, но отмечаем что ChromaDB подключён
            if not self._openai_api_key or self._openai_api_key == "sk-your-key-here":
                logger.info("skip_index_creation", reason="OpenAI API key not set. Set it in Settings page.")
                self._initialized = True  # ChromaDB connected, just no embeddings yet
                return

            # Настройка LlamaIndex embeddings
            LISettings.embed_model = OpenAIEmbedding(
                api_key=self._openai_api_key,
                model="text-embedding-3-small",
            )

            # --- HS Codes Index ---
            hs_collection = chroma_client.get_or_create_collection("hs_codes")
            hs_vector_store = ChromaVectorStore(chroma_collection=hs_collection)

            if hs_codes and hs_collection.count() == 0:
                documents = []
                for code_data in hs_codes:
                    text = f"Код ТН ВЭД: {code_data['code']}. {code_data.get('name_ru', '')}. {code_data.get('description', '')}"
                    doc = LIDocument(
                        text=text,
                        metadata={
                            "code": code_data["code"],
                            "name_ru": code_data.get("name_ru", ""),
                            "parent_code": code_data.get("parent_code", ""),
                        },
                    )
                    documents.append(doc)

                storage_ctx = StorageContext.from_defaults(vector_store=hs_vector_store)
                self.hs_codes_index = VectorStoreIndex.from_documents(
                    documents, storage_context=storage_ctx
                )
                logger.info("hs_codes_index_created", count=len(documents))
            else:
                storage_ctx = StorageContext.from_defaults(vector_store=hs_vector_store)
                self.hs_codes_index = VectorStoreIndex.from_vector_store(
                    hs_vector_store, storage_context=storage_ctx
                )
                logger.info("hs_codes_index_loaded", count=hs_collection.count())

            # --- Risk Rules Index ---
            risk_collection = chroma_client.get_or_create_collection("risk_rules")
            risk_vector_store = ChromaVectorStore(chroma_collection=risk_collection)

            if risk_rules and risk_collection.count() == 0:
                documents = []
                for rule in risk_rules:
                    text = f"Правило: {rule.get('name', '')}. {rule.get('description', '')}. Severity: {rule.get('severity', '')}. Рекомендация: {rule.get('recommendation', '')}"
                    doc = LIDocument(
                        text=text,
                        metadata={
                            "code": rule.get("code", ""),
                            "severity": rule.get("severity", ""),
                            "name": rule.get("name", ""),
                        },
                    )
                    documents.append(doc)

                storage_ctx = StorageContext.from_defaults(vector_store=risk_vector_store)
                self.risk_rules_index = VectorStoreIndex.from_documents(
                    documents, storage_context=storage_ctx
                )
                logger.info("risk_rules_index_created", count=len(documents))
            else:
                storage_ctx = StorageContext.from_defaults(vector_store=risk_vector_store)
                self.risk_rules_index = VectorStoreIndex.from_vector_store(
                    risk_vector_store, storage_context=storage_ctx
                )

            # --- Precedents Index ---
            prec_collection = chroma_client.get_or_create_collection("precedents")
            prec_vector_store = ChromaVectorStore(chroma_collection=prec_collection)
            storage_ctx = StorageContext.from_defaults(vector_store=prec_vector_store)
            self.precedents_index = VectorStoreIndex.from_vector_store(
                prec_vector_store, storage_context=storage_ctx
            )

            # --- Query Engines ---
            if self.hs_codes_index:
                hs_retriever = VectorIndexRetriever(index=self.hs_codes_index, similarity_top_k=10)
                self.hs_query_engine = RetrieverQueryEngine(retriever=hs_retriever)

            if self.risk_rules_index:
                risk_retriever = VectorIndexRetriever(index=self.risk_rules_index, similarity_top_k=5)
                self.risk_query_engine = RetrieverQueryEngine(retriever=risk_retriever)

            if self.precedents_index:
                self.precedent_retriever = VectorIndexRetriever(
                    index=self.precedents_index, similarity_top_k=5
                )

            self._initialized = True
            logger.info("index_manager_initialized")

        except Exception as e:
            logger.error("index_manager_init_failed", error=str(e), exc_info=True)
            self._initialized = False

    def search_hs_codes(self, description: str, top_k: int = 10) -> list[dict]:
        """Поиск кодов ТН ВЭД по описанию товара."""
        if not self.available or not self.hs_query_engine:
            return []

        try:
            response = self.hs_query_engine.query(
                f"Найди подходящий код ТН ВЭД для товара: {description}"
            )
            results = []
            for node in response.source_nodes:
                results.append({
                    "code": node.metadata.get("code", ""),
                    "name_ru": node.metadata.get("name_ru", ""),
                    "score": node.score or 0.0,
                    "text": node.text,
                })
            return results[:top_k]
        except Exception as e:
            logger.error("hs_search_failed", error=str(e), description=description)
            return []

    def search_risk_rules(self, declaration_text: str, top_k: int = 5) -> list[dict]:
        """Поиск релевантных правил СУР."""
        if not self.available or not self.risk_query_engine:
            return []

        try:
            response = self.risk_query_engine.query(
                f"Какие правила СУР применимы к этой декларации: {declaration_text}"
            )
            results = []
            for node in response.source_nodes:
                results.append({
                    "code": node.metadata.get("code", ""),
                    "severity": node.metadata.get("severity", ""),
                    "name": node.metadata.get("name", ""),
                    "text": node.text,
                    "score": node.score or 0.0,
                })
            return results[:top_k]
        except Exception as e:
            logger.error("risk_search_failed", error=str(e))
            return []

    def search_precedents(self, description: str, top_k: int = 5) -> list[dict]:
        """Поиск похожих прецедентов."""
        if not self.available or not self.precedent_retriever:
            return []

        try:
            nodes = self.precedent_retriever.retrieve(description)
            results = []
            for node in nodes[:top_k]:
                results.append({
                    "text": node.text,
                    "metadata": node.metadata,
                    "score": node.score or 0.0,
                })
            return results
        except Exception as e:
            logger.error("precedent_search_failed", error=str(e))
            return []

    def add_precedent(self, description: str, hs_code: str, metadata: dict = None):
        """Добавить прецедент после успешного выпуска декларации."""
        if not self.available or not self.precedents_index:
            return

        try:
            text = f"Товар: {description}. Код ТН ВЭД: {hs_code}."
            doc = LIDocument(
                text=text,
                metadata={
                    "hs_code": hs_code,
                    "description": description,
                    **(metadata or {}),
                },
            )
            self.precedents_index.insert(doc)
            logger.info("precedent_added", hs_code=hs_code, description=description[:50])
        except Exception as e:
            logger.error("precedent_add_failed", error=str(e))


# Singleton
_index_manager: Optional[IndexManager] = None


def get_index_manager() -> IndexManager:
    """Получить singleton IndexManager."""
    global _index_manager
    if _index_manager is None:
        from app.config import get_settings
        settings = get_settings()
        _index_manager = IndexManager(
            chromadb_url=settings.chromadb_url,
            openai_api_key=settings.OPENAI_API_KEY,
            openai_model=settings.OPENAI_MODEL,
        )
    return _index_manager

"""
RAG ядро: ChromaDB + OpenAI embeddings.
Индексы ТН ВЭД, правил СУР и прецедентов.
"""
import time
import uuid
from typing import Optional
import structlog

logger = structlog.get_logger()

_chromadb_available = False
try:
    import chromadb
    _chromadb_available = True
except ImportError:
    logger.warning("chromadb_not_available", msg="chromadb not installed")

_openai_available = False
try:
    import openai as _openai_mod
    _openai_available = True
except ImportError:
    logger.warning("openai_not_available", msg="openai not installed")

# Training log — in-memory ring buffer
_training_log: list[dict] = []
MAX_LOG = 200


def _log_event(event: str, detail: str = "", level: str = "info"):
    _training_log.append({
        "ts": time.time(),
        "event": event,
        "detail": detail,
        "level": level,
    })
    if len(_training_log) > MAX_LOG:
        _training_log.pop(0)
    getattr(logger, level, logger.info)(event, detail=detail)


def get_training_log() -> list[dict]:
    return list(_training_log)


class IndexManager:
    """RAG через ChromaDB + OpenAI embeddings."""

    EMBED_MODEL = "text-embedding-3-small"
    EMBED_DIM = 1536

    def __init__(self, chromadb_url: str, openai_api_key: str, openai_model: str = "gpt-4o"):
        self._chromadb_url = chromadb_url
        self._openai_api_key = openai_api_key
        self._openai_model = openai_model
        self._initialized = False
        self._chromadb_connected = False
        self._chroma_client = None
        self._openai_client = None

    # ── properties ──────────────────────────────────────────────
    @property
    def available(self) -> bool:
        return self._initialized and self._chromadb_connected and self._openai_client is not None

    @property
    def chromadb_connected(self) -> bool:
        return self._chromadb_connected

    # ── embed helper ────────────────────────────────────────────
    def _embed(self, texts: list[str]) -> list[list[float]]:
        """Get embeddings from OpenAI."""
        if not self._openai_client:
            return []
        resp = self._openai_client.embeddings.create(
            model=self.EMBED_MODEL,
            input=texts,
        )
        return [d.embedding for d in resp.data]

    def _embed_one(self, text: str) -> list[float]:
        results = self._embed([text])
        return results[0] if results else []

    # ── init ────────────────────────────────────────────────────
    def init_indices(self, hs_codes: list[dict] = None, risk_rules: list[dict] = None):
        """Connect to ChromaDB, optionally create OpenAI client."""
        if not _chromadb_available:
            _log_event("skip_init", "chromadb not installed", "warning")
            return

        try:
            host = self._chromadb_url.replace("http://", "").split(":")[0]
            port = int(self._chromadb_url.split(":")[-1])
            self._chroma_client = chromadb.HttpClient(host=host, port=port)
            self._chroma_client.heartbeat()
            self._chromadb_connected = True
            _log_event("chromadb_connected", f"{host}:{port}")
        except Exception as e:
            _log_event("chromadb_connect_failed", str(e), "error")
            return

        # OpenAI client
        if self._openai_api_key and self._openai_api_key != "sk-your-key-here" and _openai_available:
            self._openai_client = _openai_mod.OpenAI(api_key=self._openai_api_key)
            _log_event("openai_client_ready", f"model={self._openai_model}")
        else:
            _log_event("openai_not_configured", "Set key in Settings page", "warning")

        self._initialized = True

        # Index hs_codes if provided
        if hs_codes:
            self.index_hs_codes(hs_codes)

        # Index risk rules if provided
        if risk_rules:
            self._index_risk_rules(risk_rules)

    # ── HS codes ────────────────────────────────────────────────
    def index_hs_codes(self, codes: list[dict], force: bool = False) -> dict:
        """Index HS codes into ChromaDB. force=True clears collection first."""
        if not self._chroma_client:
            return {"error": "ChromaDB not connected"}

        col = self._chroma_client.get_or_create_collection(
            "hs_codes",
            metadata={"hnsw:space": "cosine"},
        )
        existing = col.count()

        if force and existing > 0:
            self._chroma_client.delete_collection("hs_codes")
            col = self._chroma_client.get_or_create_collection(
                "hs_codes",
                metadata={"hnsw:space": "cosine"},
            )
            _log_event("hs_index_cleared", f"Deleted {existing} docs")

        if not self._openai_client:
            # Store without embeddings (chromadb will use default)
            _log_event("hs_index_no_embeddings", "No OpenAI key, using default embeddings", "warning")

        BATCH = 100
        total = 0
        for i in range(0, len(codes), BATCH):
            batch = codes[i:i + BATCH]
            ids = []
            documents = []
            metadatas = []
            for c in batch:
                code = c.get("code", "")
                name = c.get("name_ru", "")
                text = f"Код ТН ВЭД: {code}. {name}"
                ids.append(f"hs_{code}")
                documents.append(text)
                metadatas.append({
                    "code": code,
                    "name_ru": name[:500] if name else "",
                    "parent_code": c.get("parent_code", "") or "",
                })

            if self._openai_client:
                embeddings = self._embed(documents)
                col.add(
                    ids=ids,
                    documents=documents,
                    metadatas=metadatas,
                    embeddings=embeddings,
                )
            else:
                col.add(ids=ids, documents=documents, metadatas=metadatas)

            total += len(batch)
            if total % 500 == 0 or total == len(codes):
                _log_event("hs_index_progress", f"{total}/{len(codes)} codes indexed")

        _log_event("hs_index_complete", f"{total} codes indexed in ChromaDB")
        return {"status": "indexed", "count": total}

    def _index_risk_rules(self, rules: list[dict]):
        """Index risk rules into ChromaDB."""
        if not self._chroma_client:
            return
        col = self._chroma_client.get_or_create_collection(
            "risk_rules",
            metadata={"hnsw:space": "cosine"},
        )
        if col.count() > 0:
            return

        ids, docs, metas = [], [], []
        for r in rules:
            text = f"Правило: {r.get('name', '')}. {r.get('description', '')}. Severity: {r.get('severity', '')}."
            rule_code = r.get("rule_code", r.get("code", uuid.uuid4().hex[:8]))
            ids.append(f"rule_{rule_code}")
            docs.append(text)
            metas.append({
                "code": str(rule_code),
                "severity": str(r.get("severity", "")),
                "name": str(r.get("name", "")),
            })

        if self._openai_client:
            embeddings = self._embed(docs)
            col.add(ids=ids, documents=docs, metadatas=metas, embeddings=embeddings)
        else:
            col.add(ids=ids, documents=docs, metadatas=metas)

        _log_event("risk_rules_indexed", f"{len(rules)} rules")

    # ── search ──────────────────────────────────────────────────
    def search_hs_codes(self, description: str, top_k: int = 10) -> list[dict]:
        """Semantic search for HS codes by goods description."""
        if not self._chroma_client:
            return []
        try:
            col = self._chroma_client.get_or_create_collection("hs_codes")
            if col.count() == 0:
                return []

            if self._openai_client:
                emb = self._embed_one(f"Товар: {description}")
                results = col.query(query_embeddings=[emb], n_results=top_k)
            else:
                # Without OpenAI, skip ChromaDB default embedding (downloads 80MB ONNX model, poor for Russian)
                logger.debug("hs_search_skipped_no_openai", description=description[:50])
                return []

            out = []
            for i, doc_id in enumerate(results["ids"][0]):
                meta = results["metadatas"][0][i] if results["metadatas"] else {}
                dist = results["distances"][0][i] if results.get("distances") else 0
                score = max(0, 1 - dist)  # cosine distance → similarity
                out.append({
                    "code": meta.get("code", ""),
                    "name_ru": meta.get("name_ru", ""),
                    "score": round(score, 4),
                    "text": results["documents"][0][i] if results["documents"] else "",
                })
            return out
        except Exception as e:
            logger.error("hs_search_failed", error=str(e))
            return []

    def search_risk_rules(self, declaration_text: str, top_k: int = 5) -> list[dict]:
        """Semantic search for risk rules."""
        if not self._chroma_client:
            return []
        try:
            col = self._chroma_client.get_or_create_collection("risk_rules")
            if col.count() == 0:
                return []

            if self._openai_client:
                emb = self._embed_one(declaration_text)
                results = col.query(query_embeddings=[emb], n_results=top_k)
            else:
                results = col.query(query_texts=[declaration_text], n_results=top_k)

            out = []
            for i, _ in enumerate(results["ids"][0]):
                meta = results["metadatas"][0][i] if results["metadatas"] else {}
                dist = results["distances"][0][i] if results.get("distances") else 0
                out.append({
                    "code": meta.get("code", ""),
                    "severity": meta.get("severity", ""),
                    "name": meta.get("name", ""),
                    "text": results["documents"][0][i] if results["documents"] else "",
                    "score": round(max(0, 1 - dist), 4),
                })
            return out
        except Exception as e:
            logger.error("risk_search_failed", error=str(e))
            return []

    def search_precedents(self, description: str, top_k: int = 5) -> list[dict]:
        """Search similar precedents."""
        if not self._chroma_client:
            return []
        try:
            col = self._chroma_client.get_or_create_collection("precedents")
            if col.count() == 0:
                return []

            if self._openai_client:
                emb = self._embed_one(description)
                results = col.query(query_embeddings=[emb], n_results=top_k)
            else:
                results = col.query(query_texts=[description], n_results=top_k)

            out = []
            for i, _ in enumerate(results["ids"][0]):
                meta = results["metadatas"][0][i] if results["metadatas"] else {}
                dist = results["distances"][0][i] if results.get("distances") else 0
                out.append({
                    "text": results["documents"][0][i] if results["documents"] else "",
                    "metadata": meta,
                    "score": round(max(0, 1 - dist), 4),
                })
            return out
        except Exception as e:
            logger.error("precedent_search_failed", error=str(e))
            return []

    def add_precedent(self, description: str, hs_code: str, metadata: dict = None):
        """Add a precedent after successful declaration release."""
        if not self._chroma_client:
            return
        try:
            col = self._chroma_client.get_or_create_collection("precedents")
            text = f"Товар: {description}. Код ТН ВЭД: {hs_code}."
            doc_id = f"prec_{uuid.uuid4().hex[:12]}"
            meta = {"hs_code": hs_code, "description": description[:500], **(metadata or {})}

            if self._openai_client:
                emb = self._embed_one(text)
                col.add(ids=[doc_id], documents=[text], metadatas=[meta], embeddings=[emb])
            else:
                col.add(ids=[doc_id], documents=[text], metadatas=[meta])

            _log_event("precedent_added", f"hs={hs_code} desc={description[:60]}")
        except Exception as e:
            logger.error("precedent_add_failed", error=str(e))

    # ── stats ───────────────────────────────────────────────────
    def get_stats(self) -> dict:
        """Return collection stats from ChromaDB."""
        stats = {
            "chromadb_connected": self._chromadb_connected,
            "openai_configured": self._openai_client is not None,
            "collections": {},
        }
        if not self._chroma_client:
            return stats
        try:
            for name in ["hs_codes", "risk_rules", "precedents"]:
                try:
                    col = self._chroma_client.get_or_create_collection(name)
                    stats["collections"][name] = col.count()
                except Exception:
                    stats["collections"][name] = -1
        except Exception as e:
            logger.error("stats_failed", error=str(e))
        return stats


# ── Singleton ───────────────────────────────────────────────────
_index_manager: Optional[IndexManager] = None


def get_index_manager() -> IndexManager:
    """Get singleton IndexManager."""
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

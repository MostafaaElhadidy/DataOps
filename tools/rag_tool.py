"""RAG tool — semantic search over Qdrant using BGE-M3 embeddings."""

from typing import Optional

from FlagEmbedding import BGEM3FlagModel
from qdrant_client import QdrantClient

from core.config import settings
from core.observability import get_logger

logger = get_logger("rag_tool")

_embed_model: Optional[BGEM3FlagModel] = None
_qdrant: Optional[QdrantClient] = None


def _embedder() -> BGEM3FlagModel:
    global _embed_model
    if _embed_model is None:
        _embed_model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=True)
    return _embed_model


def _qdrant_client() -> QdrantClient:
    global _qdrant
    if _qdrant is None:
        _qdrant = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
    return _qdrant


def _embed(text: str) -> list[float]:
    result = _embedder().encode([text], batch_size=1, max_length=512)
    return result["dense_vecs"][0].tolist()


def search_runbooks(query: str, top_k: int = 3) -> list[dict]:
    """Semantic search over the runbook collection."""
    vector = _embed(query)
    hits = _qdrant_client().search(
        collection_name=settings.qdrant_collection,
        query_vector=vector,
        limit=top_k,
        with_payload=True,
    )
    return [
        {
            "score": h.score,
            "id": str(h.id),
            "title": h.payload.get("title", ""),
            "content": h.payload.get("content", ""),
            "source": "rag",
        }
        for h in hits
    ]


def retrieve_similar_incidents(description: str, top_k: int = 3) -> list[dict]:
    """Search for similar past incidents using the same embedding space."""
    return search_runbooks(description, top_k=top_k)

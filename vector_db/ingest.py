"""Ingest runbooks and guides into the Qdrant vector store.

Run once before starting the agents:
    python -m vector_db.ingest
"""

import os
import uuid
from pathlib import Path

from FlagEmbedding import BGEM3FlagModel
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from core.config import settings
from core.observability import get_logger

logger = get_logger("ingest")

RUNBOOKS_DIR = Path(__file__).parent.parent / "runbooks"
VECTOR_SIZE = 1024  # BGE-M3 dense vector dimension


def load_documents() -> list[dict]:
    docs = []
    for path in sorted(RUNBOOKS_DIR.glob("*.md")):
        content = path.read_text(encoding="utf-8")
        # Split on ## headings to create finer-grained chunks
        chunks = _split_markdown(content, path.stem)
        docs.extend(chunks)
    logger.info("documents_loaded", count=len(docs), dir=str(RUNBOOKS_DIR))
    return docs


def _split_markdown(text: str, filename: str) -> list[dict]:
    """Split a markdown doc into per-section chunks."""
    lines = text.splitlines()
    title = lines[0].lstrip("# ").strip() if lines else filename
    chunks, current_heading, current_body = [], title, []

    for line in lines[1:]:
        if line.startswith("## "):
            if current_body:
                chunks.append(
                    {
                        "title": f"{title} — {current_heading}",
                        "content": "\n".join(current_body).strip(),
                        "source_file": filename,
                    }
                )
            current_heading = line.lstrip("# ").strip()
            current_body = []
        else:
            current_body.append(line)

    if current_body:
        chunks.append(
            {
                "title": f"{title} — {current_heading}",
                "content": "\n".join(current_body).strip(),
                "source_file": filename,
            }
        )

    # Also add the full document as a single chunk
    chunks.append({"title": title, "content": text, "source_file": filename})
    return chunks


def embed_documents(docs: list[dict]) -> list[list[float]]:
    model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=True)
    texts = [f"{d['title']}\n\n{d['content']}" for d in docs]
    logger.info("embedding_start", count=len(texts))
    result = model.encode(texts, batch_size=8, max_length=512, show_progress_bar=True)
    return result["dense_vecs"].tolist()


def ingest():
    client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
    collection = settings.qdrant_collection

    # Re-create collection for a clean ingest
    existing = [c.name for c in client.get_collections().collections]
    if collection in existing:
        client.delete_collection(collection)
        logger.info("collection_deleted", collection=collection)

    client.create_collection(
        collection_name=collection,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
    )
    logger.info("collection_created", collection=collection)

    docs = load_documents()
    vectors = embed_documents(docs)

    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=vec,
            payload=doc,
        )
        for doc, vec in zip(docs, vectors)
    ]

    client.upsert(collection_name=collection, points=points)
    logger.info("ingest_complete", points=len(points), collection=collection)
    print(f"Ingested {len(points)} chunks into '{collection}'.")


if __name__ == "__main__":
    ingest()

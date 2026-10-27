"""
Qdrant Cloud vector store — ARIA's evidence base.

The embeddings live in Qdrant Cloud, so nothing is stored on disk here. The
embedding model is still loaded locally: it is used to embed the *query*
text at search time, and must be the same model the documents were embedded
with (all-MiniLM-L6-v2, 384 dimensions).

`check_store` exists because ARIA once served a "healthy" status page while
every consultation failed: the startup check validated the LLM provider and
nothing else, so a deleted Qdrant cluster was invisible until a clinician
asked a question and got an error. The evidence base is a hard dependency
and is now probed like one.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient, models

from ingestion.embedder import load_embedding_model

logger = logging.getLogger(__name__)

__all__ = [
    "BM25_MODEL",
    "COLLECTION_NAME",
    "DENSE_VECTOR",
    "SPARSE_VECTOR",
    "HybridStore",
    "StoreReport",
    "check_store",
    "collection_name",
    "load_vectorstore",
]

#: Default collection. Overridable so a restored cluster can be pointed at a
#: new collection without a code change — the same rule `llm.config` follows
#: for model IDs.
COLLECTION_NAME = "aria_medical_v2"
#: The dense-only predecessor, kept intact as the rollback target
#: (ARIA_QDRANT_COLLECTION=aria_medical) and as the source the hybrid
#: collection is rebuilt from.
LEGACY_COLLECTION = "aria_medical"

#: Vectors are 384-dimensional (all-MiniLM-L6-v2). A collection built with a
#: different embedding model will not error — it will silently return
#: nonsense — so the probe reports the dimension for comparison.
EXPECTED_VECTOR_SIZE = 384

_CONNECT_TIMEOUT = int(os.getenv("ARIA_QDRANT_TIMEOUT", "30"))

#: Vector names in a hybrid collection (see build_hybrid_collection.py).
DENSE_VECTOR = "dense"
SPARSE_VECTOR = "bm25"
BM25_MODEL = "Qdrant/bm25"


def collection_name() -> str:
    """The collection ARIA reads from."""
    value = os.getenv("ARIA_QDRANT_COLLECTION", "").strip()
    return value or COLLECTION_NAME


def _is_local(url: str) -> bool:
    """True for a Qdrant running on this machine, which needs no API key."""
    return "localhost" in url or "127.0.0.1" in url or "://qdrant:" in url


def _credentials() -> tuple[str, str | None]:
    """Read and validate the Qdrant credentials.

    A key is required for a hosted cluster and optional for a local one, so
    a developer can run against `docker run qdrant/qdrant` without inventing
    a credential, while a misconfigured cloud deployment still fails loudly
    instead of hanging until a timeout.

    Raises:
        ValueError: if the configuration cannot reach a cluster at all.
    """
    load_dotenv()
    url = (os.getenv("QDRANT_URL") or "").strip()
    api_key = (os.getenv("QDRANT_API_KEY") or "").strip()

    if not url:
        raise ValueError(
            "Qdrant is not configured: QDRANT_URL is not set. "
            "ARIA cannot retrieve evidence without it."
        )
    if _is_local(url):
        # Never hand a cloud credential to a local, usually plain-HTTP
        # endpoint just because one happens to be left in the environment.
        return url, None
    if not api_key:
        raise ValueError(
            "Qdrant is not configured: QDRANT_API_KEY is not set for the hosted "
            f"cluster at {url}. ARIA cannot retrieve evidence without it."
        )
    return url, api_key


def get_client() -> QdrantClient:
    """A configured Qdrant client. Does not connect until first use."""
    url, api_key = _credentials()
    return QdrantClient(url=url, api_key=api_key, timeout=_CONNECT_TIMEOUT)


class HybridStore:
    """Dense + BM25 search over a hybrid collection, fused by RRF in Qdrant.

    Exposes the one method retrieval uses, `similarity_search`, so the
    navigator's balancing, reference-matter filter, reranking and floor work
    unchanged on either kind of collection.

    Why both: dense embeddings match meaning but blur exact names —
    "Can sitagliptin be used in renal impairment?" retrieved a bivalirudin
    passage and nothing about sitagliptin. BM25 matches the literal term.
    Reciprocal Rank Fusion merges the two rankings by position rather than
    by score, so neither scale has to be calibrated against the other; both
    searches and the fusion run inside one Qdrant request.
    """

    def __init__(
        self, client: QdrantClient, name: str, embeddings: Any, bm25: Any | None = None
    ) -> None:
        self.client = client
        self.name = name
        self.embeddings = embeddings
        if bm25 is None:
            from fastembed import SparseTextEmbedding

            bm25 = SparseTextEmbedding(BM25_MODEL)
        self.bm25 = bm25

    def similarity_search(self, query: str, k: int, filter: Any = None) -> list[Document]:
        dense = self.embeddings.embed_query(query)
        sparse = next(iter(self.bm25.query_embed(query)))
        result = self.client.query_points(
            self.name,
            prefetch=[
                models.Prefetch(query=dense, using=DENSE_VECTOR, limit=k, filter=filter),
                models.Prefetch(
                    query=models.SparseVector(
                        indices=sparse.indices.tolist(), values=sparse.values.tolist()
                    ),
                    using=SPARSE_VECTOR,
                    limit=k,
                    filter=filter,
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=k,
            with_payload=True,
        )
        return [
            Document(
                page_content=str((p.payload or {}).get("page_content", "")),
                metadata=dict((p.payload or {}).get("metadata") or {}),
            )
            for p in result.points
        ]


def is_hybrid(client: QdrantClient, name: str) -> bool:
    """True when the collection carries the BM25 sparse vectors."""
    sparse = client.get_collection(name).config.params.sparse_vectors or {}
    return SPARSE_VECTOR in sparse


def load_vectorstore() -> QdrantVectorStore | HybridStore:
    """Open the Qdrant-backed store used for retrieval.

    The search mode follows the collection: one built with BM25 vectors is
    searched hybrid, a dense-only one as before. Switching between them is
    therefore a matter of `ARIA_QDRANT_COLLECTION`, with no code change and
    an immediate way back.
    """
    name = collection_name()
    embeddings = load_embedding_model()
    client = get_client()
    if is_hybrid(client, name):
        logger.info("Qdrant hybrid store loaded (dense + BM25, RRF) — collection: %s", name)
        return HybridStore(client, name, embeddings)
    store = QdrantVectorStore(client=client, collection_name=name, embedding=embeddings)
    logger.info("Qdrant dense store loaded — collection: %s", name)
    return store


@dataclass(frozen=True)
class StoreReport:
    """Outcome of one evidence-base probe, for /api/health."""

    collection: str
    reachable: bool = False
    exists: bool = False
    points: int | None = None
    vector_size: int | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        """True only when the store can actually ground an answer."""
        return self.reachable and self.exists and bool(self.points)

    def as_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "collection": self.collection,
            "reachable": self.reachable,
            "exists": self.exists,
            "points": self.points,
            "vectorSize": self.vector_size,
            "error": self.error,
        }


def check_store(client: QdrantClient | None = None) -> StoreReport:
    """Probe the evidence base. Never raises — the report carries the outcome.

    An empty-but-present collection is reported as NOT ok: a store with no
    vectors cannot ground an answer, which is the condition ARIA must treat
    as an outage rather than as thin results.
    """
    name = collection_name()

    try:
        qdrant = client if client is not None else get_client()
    except ValueError as exc:
        logger.critical("VECTOR STORE: %s", exc)
        return StoreReport(collection=name, error=str(exc))

    try:
        if not qdrant.collection_exists(name):
            message = f"collection {name!r} does not exist on this cluster"
            logger.critical("VECTOR STORE: %s", message)
            return StoreReport(collection=name, reachable=True, error=message)

        info = qdrant.get_collection(name)
        points = getattr(info, "points_count", None)
        vector_size = _vector_size_of(info)
    except Exception as exc:  # a probe failure must not crash boot
        message = f"could not reach Qdrant: {exc}"
        logger.critical("=" * 72)
        logger.critical("ARIA EVIDENCE BASE UNREACHABLE — every consultation will fail")
        logger.critical("  %s", message)
        logger.critical("  Check QDRANT_URL / QDRANT_API_KEY, and that the cluster still exists.")
        logger.critical("=" * 72)
        return StoreReport(collection=name, error=message)

    report = StoreReport(
        collection=name,
        reachable=True,
        exists=True,
        points=points,
        vector_size=vector_size,
    )

    if not report.ok:
        logger.critical(
            "VECTOR STORE: collection %r exists but holds %s points — "
            "no answer can be grounded until it is repopulated.",
            name,
            points,
        )
    elif vector_size is not None and vector_size != EXPECTED_VECTOR_SIZE:
        # Not fatal, but it means queries and documents were embedded by
        # different models, and every result would be meaningless.
        logger.error(
            "VECTOR STORE: collection %r has %d-dimensional vectors, expected %d "
            "— the collection was built with a different embedding model.",
            name,
            vector_size,
            EXPECTED_VECTOR_SIZE,
        )
    else:
        logger.info(
            "VECTOR STORE OK: collection %r — %d points, %s dimensions",
            name,
            points,
            vector_size,
        )
    return report


def _vector_size_of(info: Any) -> int | None:
    """Pull the vector dimension out of a collection description.

    Qdrant reports either a single unnamed vector config or a dict of named
    ones; tolerate both, and report nothing rather than guessing.
    """
    try:
        params = info.config.params.vectors
    except AttributeError:
        return None
    size = getattr(params, "size", None)
    if isinstance(size, int):
        return size
    if isinstance(params, dict):
        for value in params.values():
            inner = getattr(value, "size", None)
            if isinstance(inner, int):
                return inner
    return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    result = check_store()
    print(f"\nevidence base ok={result.ok} {result.as_dict()}")

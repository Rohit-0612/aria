"""Hybrid retrieval: dense + BM25, fused by RRF inside one Qdrant request."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from qdrant_client import models

from retrieval.reranker import RXPREP_FILTER
from vectorstore.qdrant_store import DENSE_VECTOR, SPARSE_VECTOR, HybridStore, is_hybrid


class FakeEmbeddings:
    def embed_query(self, text: str) -> list[float]:
        return [0.1] * 384


class FakeBM25:
    def query_embed(self, text: str) -> Any:
        yield SimpleNamespace(
            indices=SimpleNamespace(tolist=lambda: [7, 42]),
            values=SimpleNamespace(tolist=lambda: [1.0, 0.5]),
        )


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def query_points(self, name: str, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        point = SimpleNamespace(
            payload={
                "page_content": "Sitagliptin: 50 mg daily if eGFR 30-45.",
                "metadata": {"book": "rxprep", "page": 598},
            }
        )
        return SimpleNamespace(points=[point])

    def get_collection(self, name: str) -> Any:
        sparse = {SPARSE_VECTOR: object()} if name == "hybrid" else None
        return SimpleNamespace(
            config=SimpleNamespace(params=SimpleNamespace(sparse_vectors=sparse))
        )


def store() -> tuple[HybridStore, FakeClient]:
    client = FakeClient()
    return HybridStore(client, "aria_medical_v2", FakeEmbeddings(), bm25=FakeBM25()), client  # type: ignore[arg-type]


def test_both_searches_are_fused_by_rrf() -> None:
    s, client = store()
    docs = s.similarity_search("can sitagliptin be used in renal impairment", k=20)

    call = client.calls[0]
    assert isinstance(call["query"], models.FusionQuery)
    assert call["query"].fusion == models.Fusion.RRF
    assert [p.using for p in call["prefetch"]] == [DENSE_VECTOR, SPARSE_VECTOR]
    assert all(p.limit == 20 for p in call["prefetch"])
    assert call["prefetch"][1].query.indices == [7, 42]
    # Returned as documents the navigator already understands.
    assert docs[0].page_content.startswith("Sitagliptin")
    assert docs[0].metadata == {"book": "rxprep", "page": 598}


def test_the_rxprep_filter_reaches_both_searches() -> None:
    """Source balancing must survive the switch to hybrid search."""
    s, client = store()
    s.similarity_search("q", k=8, filter=RXPREP_FILTER)
    assert all(p.filter == RXPREP_FILTER for p in client.calls[0]["prefetch"])


def test_mode_follows_the_collection() -> None:
    client = FakeClient()
    assert is_hybrid(client, "hybrid")  # type: ignore[arg-type]
    assert not is_hybrid(client, "dense_only")  # type: ignore[arg-type]

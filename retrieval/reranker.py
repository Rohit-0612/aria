"""
Source-balanced retrieval with Cohere reranking.

The rerank model ID comes from `llm.config` rather than being hardcoded, so
the next reranker deprecation is an environment change, not a code change.

Retrieval owns two remote dependencies — the Qdrant collection and the
Cohere reranker — and normalises a failure in either into an
`AriaRetrievalError`. It must not be reported as a language-model failure:
that sent operators to the wrong subsystem while the real cause was a
vector store that had stopped existing.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from dotenv import load_dotenv

load_dotenv()

from langchain_cohere import CohereRerank
from pydantic import SecretStr
from qdrant_client.models import FieldCondition, Filter, MatchValue

from llm.config import rerank_model
from llm.errors import EMPTY_RETRIEVAL_CODE, AriaRetrievalError, wrap_retrieval_error
from vectorstore.qdrant_store import collection_name, load_vectorstore

logger = logging.getLogger(__name__)

__all__ = ["DEFAULT_RELEVANCE_FLOOR", "BalancedRetriever", "get_balanced_retriever"]

#: Minimum Cohere relevance a passage needs to be shown as evidence.
#:
#: The reranker returns exactly `top_n` passages whether or not that many are
#: any good, so a thin query padded the citation list with whatever ranked
#: last. On a real consultation that meant four of five citations scoring
#: 0.0 — among them a book index page ("fsoprotereno! 29, 30, 93, 121") and a
#: printer footer ("CH48.indd 11 28-12-2022 14:51:10") — each displayed with
#: a page number and a relevance bar, as though it supported the answer.
#:
#: Observed scores on a well-covered question run 0.96-1.00; genuine junk
#: sits at 0.00. The floor is deliberately low: it is here to drop passages
#: the reranker itself considers irrelevant, not to second-guess it.
DEFAULT_RELEVANCE_FLOOR = 0.02


def relevance_floor() -> float:
    """Tunable without a code change, like every other retrieval knob."""
    raw = os.getenv("ARIA_RELEVANCE_FLOOR", "").strip()
    if not raw:
        return DEFAULT_RELEVANCE_FLOOR
    try:
        return max(0.0, min(1.0, float(raw)))
    except ValueError:
        logger.warning("ARIA_RELEVANCE_FLOOR=%r is not a number — using default", raw)
        return DEFAULT_RELEVANCE_FLOOR


def _relevance_of(doc: Any) -> float:
    meta = getattr(doc, "metadata", {}) or {}
    score: Any = meta.get("relevance_score", meta.get("score"))
    try:
        return float(score)
    except (TypeError, ValueError):
        # No score at all: keep the passage rather than silently dropping
        # evidence because a provider changed its metadata key.
        return 1.0


# Qdrant filter that matches only RxPrep chunks (payload field metadata.book)
RXPREP_FILTER = Filter(must=[FieldCondition(key="metadata.book", match=MatchValue(value="rxprep"))])


class BalancedRetriever:
    """
    Source-balanced retrieval across both books.

    The store holds far more DiPiro vectors than RxPrep, so a plain top-k
    search is numerically dominated by DiPiro and RxPrep never reaches the
    reranker. Here we pull a global candidate set AND a guaranteed RxPrep
    set (via metadata filter), merge them, and let Cohere rerank decide what
    is genuinely most relevant — so both books always get a fair hearing.
    """

    def __init__(
        self,
        vectorstore: Any,
        reranker: CohereRerank,
        k_global: int = 14,
        k_rxprep: int = 8,
        floor: float | None = None,
    ) -> None:
        self.vs = vectorstore
        self.reranker = reranker
        self.k_global = k_global
        self.k_rxprep = k_rxprep
        self.floor = relevance_floor() if floor is None else floor

    def invoke(self, query: str) -> list[Any]:
        """Retrieve and rerank.

        Raises:
            AriaRetrievalError: if the vector store or the reranker cannot be
                reached. Returning an empty list instead would let the
                generator answer with no evidence at all.
        """
        try:
            glob = self.vs.similarity_search(query, k=self.k_global)
            rx = self.vs.similarity_search(query, k=self.k_rxprep, filter=RXPREP_FILTER)
        except Exception as exc:
            logger.error("vector store unreachable during retrieval: %s", exc)
            raise wrap_retrieval_error(exc, "navigator", collection_name()) from exc

        seen: set[str] = set()
        candidates: list[Any] = []
        for d in glob + rx:
            key = d.page_content[:120]
            if key in seen:
                continue
            seen.add(key)
            candidates.append(d)

        if not candidates:
            # Reachable but empty: an un-restored or wrongly named collection
            # looks exactly like this, and must not pass for "no good match".
            raise AriaRetrievalError(
                stage="navigator",
                source=collection_name(),
                message="the vector store returned no candidate passages",
                code=EMPTY_RETRIEVAL_CODE,
            )

        try:
            reranked = list(self.reranker.compress_documents(candidates, query))
        except Exception as exc:
            logger.error("reranker unavailable: %s", exc)
            raise wrap_retrieval_error(exc, "navigator", "reranker") from exc
        kept = [d for d in reranked if _relevance_of(d) >= self.floor]
        if len(kept) < len(reranked):
            logger.info(
                "Dropped %d passage(s) below the %.2f relevance floor",
                len(reranked) - len(kept),
                self.floor,
            )
        if not kept:
            # The reranker judged every candidate irrelevant. Saying so is
            # more useful than answering from passages it just rejected.
            raise AriaRetrievalError(
                stage="navigator",
                source=collection_name(),
                message="no retrieved passage cleared the relevance floor",
                code=EMPTY_RETRIEVAL_CODE,
            )

        n_rx = sum(1 for d in kept if d.metadata.get("book") == "rxprep")
        logger.info(
            "Balanced retrieve: %d candidates -> %d kept (%d RxPrep, %d DiPiro)",
            len(candidates),
            len(kept),
            n_rx,
            len(kept) - n_rx,
        )
        return kept


def get_balanced_retriever(
    k_global: int = 14,
    k_rxprep: int = 8,
    top_n: int = 5,
    floor: float | None = None,
) -> BalancedRetriever:
    vectorstore: Any = load_vectorstore()
    model = rerank_model()
    api_key = os.getenv("COHERE_API_KEY")
    reranker = CohereRerank(
        model=model,
        top_n=top_n,
        cohere_api_key=SecretStr(api_key) if api_key else None,
    )
    retriever = BalancedRetriever(vectorstore, reranker, k_global, k_rxprep, floor)
    logger.info(
        "Balanced retriever ready — global %d + RxPrep %d, rerank to top %d via %s "
        "(relevance floor %.2f)",
        k_global,
        k_rxprep,
        top_n,
        model,
        retriever.floor,
    )
    return retriever


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    retriever = get_balanced_retriever()
    demo_query = "what is diabetes mellitus"

    print(f"\nQuery: {demo_query}")
    results = retriever.invoke(demo_query)

    print(f"\n-------top {len(results)} reranked chunks------")
    for i, doc in enumerate(results):
        score = doc.metadata.get("relevance_score", "N/A")
        print(f"\nRank {i + 1} (page {doc.metadata.get('page', '?')}, score: {score}):")
        print(f"{doc.page_content[:1000]}")

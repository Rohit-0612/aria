"""
Navigator agent — rewrites the query, then retrieves and reranks passages.

The query rewrite is an optimisation, not a source of clinical content: if
the rewrite model is unavailable the original question is used instead and
a warning is logged. Retrieval still runs against the real corpus, so every
passage the generator sees remains genuine.

Retrieval failures are never smoothed over — there is no safe way to answer
without sources. That includes the quiet case: retrieving *zero* passages
returns an empty list rather than an exception, and an empty list handed to
the generator becomes an empty CONTEXT block, which is an invitation to
answer from the model's own memory. ARIA's entire claim is that it does not
do that, so an empty retrieval is raised as a failure.
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Any

from llm.config import Role
from llm.errors import (
    EMPTY_RETRIEVAL_CODE,
    AriaLLMError,
    AriaRetrievalError,
    wrap_retrieval_error,
)
from llm.llm_setup import invoke_role
from retrieval.reranker import get_balanced_retriever
from vectorstore.qdrant_store import collection_name

if TYPE_CHECKING:
    from retrieval.reranker import BalancedRetriever

logger = logging.getLogger(__name__)

__all__ = ["navigator", "optimize_query"]

OPTIMIZE_PROMPT = """You are a medical search query optimizer.
Convert the user's question into a clear, concise medical search query.
Remove personal details, keep only the core medical concept.

Respond with ONLY the optimized query, nothing else.

User question: {query}

Optimized query:"""

# Built once and reused: creating it loads the embedding model and opens
# the Qdrant connection, which is far too slow to repeat per query.
#
# The lock matters because the API runs this in a worker thread: without it,
# concurrent first requests each saw `_retriever is None` and each loaded
# their own copy of the embedding model, which on a cpu-basic Space means
# several hundred MB and a stall for every one of them.
_retriever: BalancedRetriever | None = None
_retriever_lock = threading.Lock()


def optimize_query(query: str) -> str:
    """Rewrite `query` as a focused search string.

    Degrades to the original question if the rewrite model is unavailable —
    a worse search, but still a real one over real sources.
    """
    try:
        optimized = invoke_role(Role.NAVIGATOR, OPTIMIZE_PROMPT.format(query=query)).strip()
    except AriaLLMError as exc:
        logger.warning(
            "Query optimisation unavailable (%s) — retrieving with the raw question",
            exc.code or "provider error",
        )
        return query

    if not optimized:
        logger.warning("Query optimiser returned nothing — using the raw question")
        return query

    logger.info("original : %s", query)
    logger.info("optimized : %s", optimized)
    return optimized


def _get_retriever() -> BalancedRetriever:
    """The shared retriever, built at most once across threads.

    Raises:
        AriaRetrievalError: if the evidence base cannot be opened. `_retriever`
            is left unset so a later request retries, rather than latching the
            process into a permanently broken state.
    """
    global _retriever
    if _retriever is not None:
        return _retriever
    with _retriever_lock:
        if _retriever is None:  # another thread may have won the race
            try:
                _retriever = get_balanced_retriever()
            except Exception as exc:
                logger.error("could not open the evidence base: %s", exc)
                raise wrap_retrieval_error(exc, "navigator", collection_name()) from exc
    return _retriever


def navigator(query: str) -> list[Any]:
    """Retrieve the reranked passages that should ground the answer.

    Raises:
        AriaRetrievalError: if the evidence base is unreachable, or if it
            yields no passages. Never returns an empty list — the caller
            would have no way to tell "nothing matched" from "nothing was
            asked", and the generator would answer ungrounded either way.
    """
    global _retriever
    if _retriever is None:
        try:
            _retriever = get_balanced_retriever()
        except Exception as exc:
            # Left as None so a later request retries rather than latching
            # the process into a permanently broken state.
            logger.error("could not open the evidence base: %s", exc)
            raise wrap_retrieval_error(exc, "navigator", collection_name()) from exc

    chunks = _retriever.invoke(optimize_query(query))
    if not chunks:
        raise AriaRetrievalError(
            stage="navigator",
            source=collection_name(),
            message="no passages matched the query",
            code=EMPTY_RETRIEVAL_CODE,
        )

    logger.info("%d relevant chunks retrieved", len(chunks))
    return chunks


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    user_query = "My grandmother has high blood pressure, what treatment is there?"

    print("-------Navigator testing------\n")
    retrieved = navigator(user_query)

    print("--------Retrieved chunks--------\n")
    for i, doc in enumerate(retrieved):
        print(f"\nchunk {i + 1} (page {doc.metadata.get('page', '?')}):")
        print(f"{doc.page_content[:500]}")

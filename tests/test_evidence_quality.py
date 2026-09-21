"""
What is allowed to be shown as evidence, and what counts as in scope.

Both guard the same thing from different ends: the reader should only ever
be shown material the system actually stands behind.
"""

from __future__ import annotations

from typing import Any

import pytest

from llm.errors import EMPTY_RETRIEVAL_CODE, AriaRetrievalError
from retrieval.reranker import BalancedRetriever
from tests.conftest import FakeDoc


class FakeStore:
    def __init__(self, docs: list[Any]) -> None:
        self.docs = docs

    def similarity_search(self, query: str, k: int, filter: Any = None) -> list[Any]:
        return self.docs[:k]


class FakeReranker:
    """Returns its input, as Cohere does — scores already in metadata."""

    def compress_documents(self, docs: list[Any], query: str) -> list[Any]:
        return docs


def retriever_over(docs: list[Any], floor: float = 0.02) -> BalancedRetriever:
    return BalancedRetriever(FakeStore(docs), FakeReranker(), floor=floor)


def test_irrelevant_passages_are_not_shown_as_citations() -> None:
    """The padding bug.

    The reranker returns exactly top_n whether or not that many passages are
    any good. On a real consultation four of five citations scored 0.0 — a
    book index page and a printer footer among them — each displayed with a
    page number and a relevance bar as though it supported the answer.
    """
    docs = [
        FakeDoc("ARBs block the AT1 receptor.", {"relevance_score": 0.98, "book": "rxprep"}),
        FakeDoc("Thiazides act on the distal tubule.", {"relevance_score": 0.0}),
        FakeDoc("fsoprotereno! 29, 30, 93, 121 Jsopto Carpine", {"relevance_score": 0.0}),
        FakeDoc("CH48.indd 11 28-12-2022 14:51:10 AL Grawany", {"relevance_score": 0.0}),
    ]
    kept = retriever_over(docs).invoke("mechanism of action of losartan")

    assert len(kept) == 1
    assert "AT1" in kept[0].page_content


def test_a_genuinely_relevant_set_is_untouched() -> None:
    """The floor must not thin out a well-covered answer."""
    docs = [
        FakeDoc(f"passage {i}", {"relevance_score": s})
        for i, s in enumerate([1.0, 0.99, 0.5, 0.2, 0.03])
    ]
    assert len(retriever_over(docs).invoke("hypertension")) == 5


def test_everything_irrelevant_is_a_failure_not_a_thin_answer() -> None:
    """If the reranker rejected every candidate, say so.

    Answering from passages the reranker just called irrelevant would be
    exactly the ungrounded output ARIA exists to avoid.
    """
    docs = [FakeDoc("noise", {"relevance_score": 0.0}) for _ in range(5)]
    with pytest.raises(AriaRetrievalError) as caught:
        retriever_over(docs).invoke("mechanism of action of losartan")
    assert caught.value.code == EMPTY_RETRIEVAL_CODE


def test_a_passage_with_no_score_is_kept() -> None:
    """A provider changing its metadata key must not silently drop evidence."""
    docs = [FakeDoc("unscored but real", {})]
    assert len(retriever_over(docs).invoke("anything")) == 1


# ── Guardrail parsing ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("reply", "expected"),
    [
        ("YES", True),
        ("yes", True),
        ("NO", False),
        ("no", False),
        ("Answer: YES", True),
        ("Answer: NO", False),
        # The substring test matched the "yes" inside this and let it through.
        ("NO, this is not medical, yes it is off topic", False),
        # Nothing parseable: the guardrail cannot vouch for the query.
        ("I'm not sure what you mean", False),
        ("", False),
    ],
)
def test_guardrail_reads_the_first_whole_word(
    monkeypatch: pytest.MonkeyPatch, reply: str, expected: bool
) -> None:
    import agents.guardrail_agent as ga

    monkeypatch.setattr(ga, "invoke_role", lambda role, prompt: reply)
    assert ga.check_guardrail("does it matter") is expected

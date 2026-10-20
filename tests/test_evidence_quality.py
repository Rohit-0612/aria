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


# ── Reference lists ────────────────────────────────────────────────────
# Real chunks from the collection (OCR splits initial capitals: "T urnbull").

BIBLIOGRAPHY = (
    ". 2016;31(12):182 187. 95. B lackmer AB, Oertel MD, Valgus JM. Fondaparinux and "
    "the management of heparin-induced thrombocytopenia: The journey continues. Ann "
    "Pharmacother. 2009;43(10):1636 1646. 96. W arkentin TE, Pai M, Sheppard JI, et al. "
    "Fondaparinux treatment of acute heparin-induced thrombocytopenia confirmed by the "
    "serotonin-release assay. J Thromb Haemost. 2011;9(12):2389 2396. 97. L insenmeyer K, "
    "et al. Fondaparinux in HIT. Thromb Res. 2018;164:33 38. 10.1016/j.thromres.2018.02.001 "
    "29475123."
)
PROSE = (
    "Argatroban is a direct thrombin inhibitor given by continuous infusion. It is "
    "hepatically eliminated, so it is preferred in renal impairment, and the aPTT is "
    "monitored to a target of 1.5 to 3 times baseline. Warfarin should not be started "
    "until the platelet count has recovered to at least 150,000/mm3, because protein C "
    "depletion can precipitate venous limb gangrene (Warkentin et al., 2011)."
)


def test_a_reference_list_is_recognised() -> None:
    from retrieval.reranker import is_bibliography

    assert is_bibliography(BIBLIOGRAPHY)


def test_clinical_prose_with_an_inline_citation_is_kept() -> None:
    from retrieval.reranker import is_bibliography

    assert not is_bibliography(PROSE)


def test_reference_lists_never_reach_the_reranker() -> None:
    """The HIT failure: five reference lists, each scored 1.00 by the reranker."""
    seen: list[str] = []

    class Recording(FakeReranker):
        def compress_documents(self, docs: list[Any], query: str) -> list[Any]:
            seen.extend(d.page_content for d in docs)
            return docs

    docs = [
        FakeDoc(BIBLIOGRAPHY, {"relevance_score": 1.0}),
        FakeDoc(PROSE, {"relevance_score": 0.9}),
    ]
    kept = BalancedRetriever(FakeStore(docs), Recording()).invoke("how is HIT managed?")

    assert seen == [PROSE]
    assert [d.page_content for d in kept] == [PROSE]


def test_only_reference_lists_is_an_empty_retrieval() -> None:
    docs = [FakeDoc(BIBLIOGRAPHY, {"relevance_score": 1.0})]
    with pytest.raises(AriaRetrievalError) as err:
        retriever_over(docs).invoke("how is HIT managed?")
    assert err.value.code == EMPTY_RETRIEVAL_CODE
    assert "reference lists and index pages" in str(err.value)


INDEX_PAGE = (
    "INDEX 2597 Hemorrhagic stroke, 283 etiology of, 283 284 pathophysiology of, 285 "
    "treatment of, 288 Heparin, 412, 415t, 418 low-molecular-weight, 420, 1717 1725 "
    "unfractionated, 413 Heparin-induced thrombocytopenia, 2361, 2364 Hepatitis B, 1022"
)
DOSAGE_TABLE = (
    "Sodium citrate/citric acid 1 mL contains 1 mEq sodium and is equivalent to 1 mEq "
    "bicarbonate. Solution, sodium citrate 500 mg, citric acid 334 mg per 5 mL. Dose 10 "
    "to 30 mL, 4 times daily, diluted in water, after meals and at bedtime."
)


def test_an_index_page_is_recognised() -> None:
    from retrieval.reranker import is_index_page

    assert is_index_page(INDEX_PAGE)


def test_a_dosage_table_is_not_an_index() -> None:
    """The densest numeric prose in the corpus, and real clinical content."""
    from retrieval.reranker import is_reference_matter

    assert not is_reference_matter(DOSAGE_TABLE)
    assert not is_reference_matter(PROSE)

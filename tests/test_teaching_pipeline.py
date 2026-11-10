"""
The teaching pipeline: outline planning, facet retrieval, sentence
completion, the Gemini generator cascade and the budget-aware Judge.

Every provider is faked. What is pinned is the behaviour that keeps the
answer honest and the app up: a facet is never crowded out, the reranker is
called once per question, a citation number always means the same passage,
a failing model is skipped before the reader sees any text, and a half
answer is never passed off as a whole one.
"""

from __future__ import annotations

from typing import Any

import pytest

from llm.errors import AriaLLMError
from tests.conftest import FakeDoc

# ── Planner ────────────────────────────────────────────────────────────


def test_planner_parses_facets_and_drops_duplicates(monkeypatch: pytest.MonkeyPatch) -> None:
    import retrieval.planner as planner

    reply = (
        '{"facets": [{"name": "Definition", "query": "localized prostate cancer"},'
        ' {"name": "Same", "query": "Localized Prostate Cancer"},'
        ' {"name": "ADT adverse effects", "query": "androgen deprivation adverse effects"},'
        ' {"name": "", "query": "nameless"}]}'
    )
    monkeypatch.setattr(planner, "invoke_role", lambda *a, **k: reply)
    facets = planner.plan_facets("q")
    assert [f.name for f in facets] == ["Definition", "ADT adverse effects"]


@pytest.mark.parametrize("reply", ["not json", '{"facets": [{"name": "Only", "query": "one"}]}'])
def test_planner_with_no_usable_plan_falls_back(
    monkeypatch: pytest.MonkeyPatch, reply: str
) -> None:
    import retrieval.planner as planner

    monkeypatch.setattr(planner, "invoke_role", lambda *a, **k: reply)
    assert planner.plan_facets("q") == []


def test_planner_outage_is_not_a_failed_consultation(monkeypatch: pytest.MonkeyPatch) -> None:
    import retrieval.planner as planner

    def down(*a: Any, **k: Any) -> str:
        raise AriaLLMError("navigator", "m", "gone", "model_not_found")

    monkeypatch.setattr(planner, "invoke_role", down)
    assert planner.plan_facets("q") == []


# ── Facet retrieval ────────────────────────────────────────────────────


class FakeStore:
    """Returns canned passages per query; RxPrep searches return nothing."""

    def __init__(self, by_query: dict[str, list[FakeDoc]]) -> None:
        self.by_query = by_query

    def similarity_search(self, query: str, k: int, filter: Any = None) -> list[FakeDoc]:
        return [] if filter is not None else self.by_query.get(query, [])[:k]


class FakeReranker:
    def __init__(self, scores: dict[str, float]) -> None:
        self.scores = scores
        self.calls = 0

    def rerank(self, documents: list[str], query: str, top_n: int = -1) -> list[dict[str, Any]]:
        self.calls += 1
        return [
            {"index": i, "relevance_score": self.scores.get(d, 0.0)}
            for i, d in enumerate(documents)
        ]


def _retriever(store: FakeStore, reranker: FakeReranker) -> Any:
    from retrieval.reranker import BalancedRetriever

    return BalancedRetriever(store, reranker, floor=0.02)  # type: ignore[arg-type]


def test_every_facet_keeps_its_passages_and_reranking_is_one_call() -> None:
    treat = [FakeDoc(f"treatment passage {i}", {"book": "dipiro"}) for i in range(6)]
    safety = [FakeDoc(f"adverse effect passage {i}", {"book": "dipiro"}) for i in range(3)]
    # The main topic outscores everything: a plain top-k would be all treatment.
    scores = {d.page_content: 0.9 for d in treat} | {d.page_content: 0.2 for d in safety}
    reranker = FakeReranker(scores)
    r = _retriever(FakeStore({"treat q": treat, "safety q": safety}), reranker)

    out = r.invoke_facets(
        "question", [("Treatment", "treat q"), ("Safety", "safety q")], per_facet=2, cap=5
    )

    texts = [d.page_content for d in out]
    assert reranker.calls == 1
    assert len(out) == 5
    assert sum("adverse" in t for t in texts) >= 2, "the safety facet was crowded out"
    assert texts[:2] == ["treatment passage 0", "treatment passage 1"]  # facet order is kept
    assert all("relevance_score" in d.metadata for d in out)


def test_facet_retrieval_drops_passages_below_the_floor() -> None:
    good = FakeDoc("relevant passage", {"book": "dipiro"})
    junk = FakeDoc("irrelevant passage", {"book": "dipiro"})
    r = _retriever(FakeStore({"q": [good, junk]}), FakeReranker({"relevant passage": 0.5}))
    out = r.invoke_facets("question", [("A", "q"), ("B", "q2")])
    assert [d.page_content for d in out] == ["relevant passage"]


def test_navigate_falls_back_to_one_search_without_a_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    import agents.navigator_agent as nav

    class OneSearch:
        vs = None

        def invoke(self, query: str) -> list[Any]:
            return [FakeDoc("passage", {"book": "dipiro"})]

    monkeypatch.setenv("ARIA_FACET_RETRIEVAL", "1")
    monkeypatch.setattr(nav, "_retriever", OneSearch())
    monkeypatch.setattr(nav, "plan_facets", lambda q: [])
    monkeypatch.setattr(nav, "optimize_query", lambda q: q)
    r = nav.navigate("q")
    assert r.outline == [] and len(r.chunks) == 1


# ── Sentence completion ────────────────────────────────────────────────


class FakePoint:
    def __init__(self, text: str, page: int) -> None:
        self.payload = {"page_content": text, "metadata": {"book": "dipiro", "page": page}}


class FakeClient:
    def __init__(self, points: list[FakePoint], fail: Exception | None = None) -> None:
        self.points = points
        self.fail = fail

    def scroll(self, collection: str, **kw: Any) -> tuple[list[FakePoint], None]:
        if self.fail:
            raise self.fail
        return self.points, None


class StoreWith:
    def __init__(self, client: FakeClient) -> None:
        self.client = client
        self.name = "col"


def test_a_passage_cut_mid_sentence_is_completed_from_its_neighbours() -> None:
    import retrieval.context_window as cw

    cw._NO_PAGE_INDEX = False
    # Neighbours overlap this chunk by a few dozen characters, as the splitter
    # leaves them (its overlap is "up to" 200, often less).
    prev = (
        "Earlier text. Androgen deprivation is the backbone of therapy for advanced disease and is"
    )
    mine = "of therapy for advanced disease and is continued in all cases while a second agent is"
    nxt = "in all cases while a second agent is added on top. Later text."
    store = StoreWith(FakeClient([FakePoint(prev, 7), FakePoint(mine, 7), FakePoint(nxt, 7)]))
    doc = FakeDoc(mine, {"book": "dipiro", "page": 7})
    [out] = cw.complete_passages([doc], store)
    assert out.page_content.startswith("Androgen deprivation is the backbone")
    assert out.page_content.endswith("is added on top.")


def test_without_a_page_index_only_the_stray_punctuation_goes() -> None:
    import retrieval.context_window as cw

    cw._NO_PAGE_INDEX = False
    store = StoreWith(
        FakeClient([], fail=RuntimeError("Bad request: Index required but not found"))
    )
    doc = FakeDoc(". However, for patients with disease", {"book": "dipiro", "page": 1})
    [out] = cw.complete_passages([doc], store)
    assert out.page_content.startswith("However, for patients")
    assert cw._NO_PAGE_INDEX is True  # and the failing request is not repeated
    cw._NO_PAGE_INDEX = False


# ── Generator cascade ──────────────────────────────────────────────────


@pytest.fixture
def cascade(monkeypatch: pytest.MonkeyPatch) -> Any:
    import llm.generator as gen

    monkeypatch.setattr(gen, "gemini_key", lambda: "k")
    monkeypatch.setattr(gen, "_cooling_until", {})
    monkeypatch.setenv("ARIA_GENERATOR_CASCADE", "busy-model,good-model")
    return gen


def test_a_failing_model_is_skipped_before_any_text(
    cascade: Any, monkeypatch: pytest.MonkeyPatch, chunks: list[Any]
) -> None:
    from llm.gemini import GeminiError

    def fake(model: str, prompt: str, **k: Any) -> Any:
        if model == "busy-model":
            raise GeminiError("overloaded", "503")
        return iter(["Thiazides ", "are first-line [[1]]."])

    monkeypatch.setattr(cascade, "stream_gemini", fake)
    used: list[str] = []
    text = "".join(cascade.stream_answer("q", chunks, ["Treatment"], used.append))
    assert text == "Thiazides are first-line [[1]]."
    assert used == ["good-model"]
    assert not cascade._available("busy-model")  # cooled down, not retried next turn


def test_every_gemini_model_failing_falls_back_to_groq_keeping_numbers(
    cascade: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from llm.gemini import GeminiError

    def down(model: str, prompt: str, **k: Any) -> Any:
        raise GeminiError("quota", "429")

    seen: dict[str, str] = {}

    def groq(role: Any, prompt: str) -> Any:
        seen["prompt"] = prompt
        return iter(["Written on Groq [[3]]."])

    many = [FakeDoc("x" * 4000, {"relevance_score": s}) for s in (0.1, 0.2, 0.9, 0.3, 0.8)]
    monkeypatch.setattr(cascade, "stream_gemini", down)
    monkeypatch.setattr(cascade, "stream_role", groq)
    text = "".join(cascade.stream_answer("q", many, ["Treatment"]))
    assert text == "Written on Groq [[3]]."
    # The budget kept the two most relevant passages, under their own numbers.
    assert "[3] " in seen["prompt"] and "[5] " in seen["prompt"]
    assert "[1] " not in seen["prompt"]


def test_a_model_failing_mid_answer_is_an_error_not_a_short_answer(
    cascade: Any, monkeypatch: pytest.MonkeyPatch, chunks: list[Any]
) -> None:
    from llm.gemini import GeminiError

    def dies(model: str, prompt: str, **k: Any) -> Any:
        yield "Thiazides "
        raise GeminiError("network", "reset", started=True)

    monkeypatch.setattr(cascade, "stream_gemini", dies)
    with pytest.raises(AriaLLMError):
        "".join(cascade.stream_answer("q", chunks, ["Treatment"]))


def test_a_model_failing_mid_answer_is_rewritten_by_the_next_when_the_caller_can_take_it_back(
    cascade: Any, monkeypatch: pytest.MonkeyPatch, chunks: list[Any]
) -> None:
    from llm.gemini import GeminiError

    def fake(model: str, prompt: str, **k: Any) -> Any:
        if model == "busy-model":
            yield "Half an ans"
            raise GeminiError("overloaded", "timed out", started=True)
        yield "A whole answer [[1]]."

    monkeypatch.setattr(cascade, "stream_gemini", fake)
    restarts: list[str] = []
    seen: list[str] = []
    for piece in cascade.stream_answer("q", chunks, ["Treatment"], on_restart=restarts.append):
        seen.append(piece)
    assert restarts == ["busy-model"]
    assert seen == ["Half an ans", "A whole answer [[1]]."]  # the caller drops the first
    assert not cascade._available("busy-model")
    # The batch form never returns the two joined up.
    monkeypatch.setattr(cascade, "_cooling_until", {})
    assert cascade.generate_answer("q", chunks, ["Treatment"]) == "A whole answer [[1]]."


def test_without_an_outline_the_original_prompt_and_groq_are_used(
    cascade: Any, monkeypatch: pytest.MonkeyPatch, chunks: list[Any]
) -> None:
    def never(*a: Any, **k: Any) -> Any:
        raise AssertionError("Gemini was called for the single-search pipeline")

    seen: dict[str, str] = {}
    monkeypatch.setattr(cascade, "stream_gemini", never)
    monkeypatch.setattr(
        cascade, "stream_role", lambda role, p: seen.setdefault("p", p) and iter(["ok"])
    )
    assert "".join(cascade.stream_answer("q", chunks)) == "ok"
    assert "## OUTLINE" not in seen["p"]


# ── Judge ──────────────────────────────────────────────────────────────


def test_judge_retries_a_json_mode_rejection_without_json_mode(
    monkeypatch: pytest.MonkeyPatch, chunks: list[Any]
) -> None:
    import agents.judge_agent as judge

    calls: list[bool] = []

    def invoke(role: Any, prompt: str, *, json_mode: bool = False, model: Any = None) -> str:
        calls.append(json_mode)
        if json_mode:
            raise AriaLLMError("judge", "m", "bad json", "json_validate_failed")
        return '{"confidence": 0.8, "reason": "supported"}'

    monkeypatch.setattr(judge, "invoke_role", invoke)
    verdict = judge.judge_answer("q", "Thiazides [[1]].", chunks)
    assert verdict.confidence == 0.8
    assert calls == [True, False]


def test_judge_is_told_which_cited_passages_were_left_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import agents.judge_agent as judge

    big = [
        FakeDoc("y" * (judge.JUDGE_PASSAGE_CHARS // 3), {"relevance_score": s})
        for s in (0.9, 0.8, 0.7, 0.1)
    ]
    seen: dict[str, str] = {}

    def invoke(role: Any, prompt: str, *, json_mode: bool = False, model: Any = None) -> str:
        seen["p"] = prompt
        return '{"confidence": 0.9, "reason": "ok"}'

    monkeypatch.setattr(judge, "invoke_role", invoke)
    judge.judge_answer("q", "A [[1]]. B [[2]]. C [[3]]. D [[4]].", big)
    assert "Passages [4] are cited and do exist but are not shown" in seen["p"]
    assert "[4] " not in seen["p"].split("CONTEXT:")[1].split("QUESTION:")[0]


def test_judge_sees_only_cited_passages_when_they_exceed_its_budget() -> None:
    from agents.judge_agent import JUDGE_PASSAGE_CHARS, _judged_passages

    big = [FakeDoc("y" * (JUDGE_PASSAGE_CHARS // 3), {"relevance_score": 0.5}) for _ in range(6)]
    keep = _judged_passages("Claim [[2]]. Claim [[5]].", big)
    assert keep == {2, 5}


def test_a_rate_limited_judge_scores_on_the_spare_model(
    monkeypatch: pytest.MonkeyPatch, chunks: list[Any]
) -> None:
    import agents.judge_agent as judge

    models: list[Any] = []

    def invoke(role: Any, prompt: str, *, json_mode: bool = False, model: Any = None) -> str:
        models.append(model)
        if model is None:
            raise AriaLLMError("judge", "openai/gpt-oss-120b", "429", "rate_limit_exceeded")
        return '{"confidence": 0.7, "reason": "ok"}'

    monkeypatch.setattr(judge, "invoke_role", invoke)
    assert judge.judge_answer("q", "Thiazides [[1]].", chunks).confidence == 0.7
    assert models == [None, "openai/gpt-oss-20b"]


# ── Gemini client ──────────────────────────────────────────────────────


class _FakeSSE:
    def __init__(self, events: list[dict[str, Any]]) -> None:
        import json

        self.status_code = 200
        self.lines = [f"data: {json.dumps(e)}" for e in events]

    def __enter__(self) -> _FakeSSE:
        return self

    def __exit__(self, *a: Any) -> None:
        return None

    def iter_lines(self) -> Any:
        return iter(self.lines)


def _text(t: str, finish: str | None = None) -> dict[str, Any]:
    cand: dict[str, Any] = {"content": {"parts": [{"text": t}]}}
    if finish:
        cand["finishReason"] = finish
    return {"candidates": [cand]}


@pytest.mark.parametrize("last", [None, "MAX_TOKENS"])
def test_a_reply_that_ends_without_stop_is_incomplete_not_short(
    monkeypatch: pytest.MonkeyPatch, last: str | None
) -> None:
    """Seen live: 14 words, then the stream closed with no error."""
    import llm.gemini as g
    from llm.gemini import GeminiError

    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setattr(
        g.httpx, "stream", lambda *a, **k: _FakeSSE([_text("**In short:** Initial ", last)])
    )
    with pytest.raises(GeminiError) as caught:
        list(g.stream_gemini("m", "p"))
    assert caught.value.kind == "incomplete" and caught.value.started


def test_a_reply_that_ends_with_stop_is_whole(monkeypatch: pytest.MonkeyPatch) -> None:
    import llm.gemini as g

    monkeypatch.setenv("GEMINI_API_KEY", "k")
    events = [_text("Thiazides "), _text("are first-line [[1]].", "STOP")]
    monkeypatch.setattr(g.httpx, "stream", lambda *a, **k: _FakeSSE(events))
    assert "".join(g.stream_gemini("m", "p")) == "Thiazides are first-line [[1]]."

"""
Inline citations and follow-up questions.

Two promises the interface makes, pinned end to end:

  * an inline `[[n]]` marker opens passage n. That only holds if the
    generator, the judge and the browser all number the passages the same
    way, and the browser has them before the prose that cites them arrives;
  * a follow-up ("and in pregnancy?") is understood against the
    conversation, without the conversation ever becoming evidence.
"""

from __future__ import annotations

import json
import threading
import time
from typing import Any

import pytest
from pydantic import ValidationError

from agents import context_agent
from agents.context_agent import resolve_followup
from api.server import (
    MAX_HISTORY_TURNS,
    MAX_QUERY_CHARS,
    ConsultRequest,
    run_consultation,
)
from llm.errors import AriaLLMError
from llm.generator import format_passages
from tests.conftest import FakeDoc


async def collect(query: str, history: list[Any] | None = None) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    async for raw in run_consultation(query, history):
        events.append(json.loads(raw[len("data: ") :]))
    return events


@pytest.fixture
def pipeline(monkeypatch: pytest.MonkeyPatch, chunks: list[Any]) -> dict[str, list[str]]:
    """Patch every model call; record the question each stage was given."""
    from agents.judge_agent import Judgment

    seen: dict[str, list[str]] = {"guardrail": [], "navigator": [], "generator": []}

    def guard(q: str) -> bool:
        seen["guardrail"].append(q)
        return True

    def nav(q: str) -> list[Any]:
        seen["navigator"].append(q)
        return chunks

    def gen(q: str, c: list[Any]) -> Any:
        seen["generator"].append(q)
        return iter(["Thiazides are first-line [[1]].", " ACE inhibitors help [[2]]."])

    monkeypatch.setattr("graph.nodes.check_guardrail", guard)
    monkeypatch.setattr("graph.nodes.navigator", nav)
    monkeypatch.setattr("graph.nodes.stream_answer", gen)
    monkeypatch.setattr("graph.nodes.judge_answer", lambda q, a, c: Judgment(0.9, "ok"))
    return seen


# ── Shared numbering ───────────────────────────────────────────────────


def test_passages_are_numbered_with_book_and_page(chunks: list[Any]) -> None:
    text = format_passages(chunks)
    assert text.startswith("[1] DiPiro's Pharmacotherapy 12e, p. 412\nThiazide")
    assert "\n\n[2] RxPrep NAPLEX 2025, p. 88\nACE inhibitors" in text


def test_untagged_passages_are_dipiro() -> None:
    """DiPiro was ingested before the `book` tag existed."""
    assert format_passages([FakeDoc("x", {"page": 3})]).startswith("[1] DiPiro")


@pytest.mark.asyncio
async def test_sources_arrive_before_the_prose_that_cites_them(pipeline: Any) -> None:
    events = await collect("What is first-line therapy for hypertension?")
    kinds = [e["type"] for e in events]

    assert kinds.index("sources") < kinds.index("token")
    sources = next(e for e in events if e["type"] == "sources")
    meta = next(e for e in events if e["type"] == "meta")
    # Same numbering in both, and it is the order the generator was given.
    assert [c["marker"] for c in sources["citations"]] == [1, 2]
    assert sources["citations"] == meta["citations"]
    assert sources["citations"][1]["book"] == "rxprep"
    # Nothing graded travels with the early sources.
    assert "confidence" not in sources and "evidenceTier" not in sources


# ── Follow-ups ─────────────────────────────────────────────────────────

HISTORY = [
    {"role": "user", "content": "What is first-line therapy for hypertension?"},
    {"role": "assistant", "content": "Thiazide diuretics are first-line [[1]]."},
]


def test_no_history_means_no_model_call(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_: Any) -> str:
        raise AssertionError("model called without a conversation")

    monkeypatch.setattr(context_agent, "invoke_role", boom)
    assert resolve_followup("and in pregnancy?", []) == "and in pregnancy?"


def test_followup_is_rewritten_with_the_conversation(monkeypatch: pytest.MonkeyPatch) -> None:
    prompts: list[str] = []

    def fake(_role: Any, prompt: str) -> str:
        prompts.append(prompt)
        return "Which antihypertensives are safe in pregnancy?"

    monkeypatch.setattr(context_agent, "invoke_role", fake)
    out = resolve_followup("and in pregnancy?", HISTORY)  # type: ignore[arg-type]

    assert out == "Which antihypertensives are safe in pregnancy?"
    assert "User: What is first-line therapy for hypertension?" in prompts[0]
    assert "FOLLOW-UP: and in pregnancy?" in prompts[0]


def test_long_replies_are_clipped_in_the_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    prompts: list[str] = []
    monkeypatch.setattr(
        context_agent, "invoke_role", lambda _r, p: prompts.append(p) or "standalone?"
    )
    long_turn = [{"role": "assistant", "content": "word " * 2000}]
    resolve_followup("and the dose?", long_turn)  # type: ignore[arg-type]
    assert len(prompts[0]) < 2500


@pytest.mark.parametrize("reply", ["", "x" * 2000])
def test_unusable_rewrite_falls_back_to_the_question(
    monkeypatch: pytest.MonkeyPatch, reply: str
) -> None:
    """Empty, or ballooned into an answer instead of a question."""
    monkeypatch.setattr(context_agent, "invoke_role", lambda _r, _p: reply)
    assert resolve_followup("and the dose?", HISTORY) == "and the dose?"  # type: ignore[arg-type]


def test_unreachable_rewrite_falls_back_to_the_question(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def down(*_: Any) -> str:
        raise AriaLLMError("navigator", "openai/gpt-oss-20b", "down", "rate_limited")

    monkeypatch.setattr(context_agent, "invoke_role", down)
    assert resolve_followup("and the dose?", HISTORY) == "and the dose?"  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_every_stage_answers_the_standalone_question(
    monkeypatch: pytest.MonkeyPatch, pipeline: dict[str, list[str]]
) -> None:
    standalone = "Which antihypertensives are safe in pregnancy?"
    monkeypatch.setattr("graph.nodes.resolve_followup", lambda q, h: standalone)

    events = await collect("and in pregnancy?", HISTORY)

    assert pipeline == {
        "guardrail": [standalone],
        "navigator": [standalone],
        "generator": [standalone],
    }
    # The reader is shown how their follow-up was understood.
    guard = [s for s in events if s["type"] == "steps"][-1]["steps"][0]
    assert guard["detail"] == f"Follow-up read as: {standalone}"


@pytest.mark.asyncio
async def test_first_question_reports_no_rewrite(pipeline: dict[str, list[str]]) -> None:
    events = await collect("What is first-line therapy for hypertension?")
    guard = [s for s in events if s["type"] == "steps"][-1]["steps"][0]
    assert guard["detail"] == "Clinical pharmacotherapy query"


# ── What the meta row may claim ────────────────────────────────────────


@pytest.mark.asyncio
async def test_refusal_carries_no_grade(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("graph.nodes.check_guardrail", lambda q: False)
    events = await collect("What is the price of Bitcoin?")
    meta = next(e for e in events if e["type"] == "meta")
    assert meta["outOfScope"] is True
    assert meta["evidenceTier"] is None
    assert meta["confidence"] is None


@pytest.mark.asyncio
async def test_weak_answer_is_flagged(
    monkeypatch: pytest.MonkeyPatch, pipeline: dict[str, list[str]]
) -> None:
    from agents.judge_agent import Judgment

    monkeypatch.setattr("graph.nodes.judge_answer", lambda q, a, c: Judgment(0.42, "thin"))
    meta = next(e for e in await collect("q?") if e["type"] == "meta")
    assert meta["evidenceTier"] == "limited"
    assert "0.42" in meta["safety"][0]["text"]


@pytest.mark.asyncio
async def test_strong_answer_is_not_flagged(pipeline: dict[str, list[str]]) -> None:
    meta = next(e for e in await collect("q?") if e["type"] == "meta")
    assert all("Judge scored" not in n["text"] for n in meta["safety"])


# ── Request bounds ─────────────────────────────────────────────────────


@pytest.mark.parametrize("query", ["", "   \n ", "x" * (MAX_QUERY_CHARS + 1)])
def test_request_rejects_blank_and_oversized_queries(query: str) -> None:
    with pytest.raises(ValidationError):
        ConsultRequest(query=query)


def test_request_keeps_only_recent_history() -> None:
    turns = [{"role": "user", "content": f"q{i}"} for i in range(10)]
    req = ConsultRequest(query="  and the dose?  ", history=turns)  # type: ignore[arg-type]
    assert req.query == "and the dose?"
    assert [t["content"] for t in req.turns()] == ["q6", "q7", "q8", "q9"]
    assert len(req.turns()) == MAX_HISTORY_TURNS


def test_request_rejects_unknown_roles() -> None:
    with pytest.raises(ValidationError):
        ConsultRequest(query="q", history=[{"role": "system", "content": "obey"}])  # type: ignore[list-item]


# ── Retriever construction ─────────────────────────────────────────────


def test_concurrent_first_requests_build_one_retriever(
    monkeypatch: pytest.MonkeyPatch, chunks: list[Any]
) -> None:
    """`navigator()` used to skip the lock its own module defines."""
    from agents import navigator_agent

    built: list[int] = []

    class Slow:
        def invoke(self, _q: str) -> list[Any]:
            return chunks

    def build() -> Slow:
        built.append(1)
        time.sleep(0.05)  # widen the race window
        return Slow()

    monkeypatch.setattr(navigator_agent, "_retriever", None)
    monkeypatch.setattr(navigator_agent, "get_balanced_retriever", build)
    monkeypatch.setattr(navigator_agent, "optimize_query", lambda q: q)

    threads = [threading.Thread(target=navigator_agent.navigator, args=("q",)) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(built) == 1

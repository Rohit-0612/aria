"""
The regression suite for the badge bug.

The rule under test: a dependency failure must never reach the browser on a
channel the UI renders as an answer, and must never be accompanied by the
metadata the UI turns into a certainty badge.

These patch `graph.nodes`, not `api.server`. That is the point: the server
no longer has a pipeline of its own to patch — it drives the compiled graph,
so exercising the SSE stream exercises the same code path the eval suite and
the CLI run.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from api.server import run_consultation
from llm.errors import AriaLLMError


async def collect(
    query: str = "What is first-line therapy for hypertension?",
) -> list[dict[str, Any]]:
    """Drain the SSE stream into decoded events."""
    events: list[dict[str, Any]] = []
    async for raw in run_consultation(query):
        assert raw.startswith("data: ")
        events.append(json.loads(raw[len("data: ") :]))
    return events


def types_of(events: list[dict[str, Any]]) -> list[str]:
    return [e["type"] for e in events]


def steps_at_end(events: list[dict[str, Any]]) -> dict[str, str]:
    last = [e for e in events if e["type"] == "steps"][-1]
    return {s["id"]: s["status"] for s in last["steps"]}


@pytest.fixture
def happy_path(monkeypatch: pytest.MonkeyPatch, chunks: list[Any]) -> None:
    from agents.judge_agent import Judgment

    monkeypatch.setattr("graph.nodes.check_guardrail", lambda q: True)
    monkeypatch.setattr("graph.nodes.navigator", lambda q: chunks)
    monkeypatch.setattr(
        "graph.nodes.stream_answer", lambda q, c: iter(["Thiazides ", "are first-line."])
    )
    monkeypatch.setattr("graph.nodes.judge_answer", lambda q, a, c: Judgment(0.88, "grounded"))


@pytest.mark.asyncio
async def test_happy_path_emits_meta_and_tokens(happy_path: None) -> None:
    events = await collect()
    kinds = types_of(events)
    assert "meta" in kinds
    assert "token" in kinds
    assert "error" not in kinds

    meta = next(e for e in events if e["type"] == "meta")
    assert meta["evidenceTier"] == "strong"
    assert meta["confidence"] == 0.88
    assert len(meta["citations"]) == 2
    assert steps_at_end(events)["judge"] == "done"


@pytest.mark.asyncio
async def test_generator_failure_emits_no_token_and_no_meta(
    monkeypatch: pytest.MonkeyPatch, chunks: list[Any]
) -> None:
    """THE regression test.

    Before the fix the exception text was streamed as a `token` with no
    `meta`, so the UI kept its seeded 'moderate' tier and stamped
    "MODERATE CERTAINTY · grounded reply" onto a provider error.
    """
    monkeypatch.setattr("graph.nodes.check_guardrail", lambda q: True)
    monkeypatch.setattr("graph.nodes.navigator", lambda q: chunks)

    def dead(q: str, c: list[Any]) -> Any:
        raise AriaLLMError("generator", "llama-3.3-70b-versatile", "gone", "model_not_found")
        yield ""  # pragma: no cover - makes `dead` a generator function

    monkeypatch.setattr("graph.nodes.stream_answer", dead)

    events = await collect()
    kinds = types_of(events)

    assert "token" not in kinds, "a failure must never travel as answer prose"
    assert "meta" not in kinds, "a failure must never carry badge metadata"
    assert kinds.count("error") == 1
    assert kinds[-1] == "done"

    err = next(e for e in events if e["type"] == "error")
    assert err["stage"] == "generator"
    assert err["code"] == "model_not_found"
    assert "No clinical content was generated." in err["message"]

    statuses = steps_at_end(events)
    assert statuses["generator"] == "failed"
    assert statuses["judge"] == "skipped"


@pytest.mark.asyncio
async def test_guardrail_failure_does_not_fail_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A dead guardrail must stop the turn, not silently allow the query."""
    reached = {"navigator": False}

    def dead(q: str) -> bool:
        raise AriaLLMError("guardrail", "m", "gone", "model_not_found")

    def spy(q: str) -> list[Any]:
        reached["navigator"] = True
        return []

    monkeypatch.setattr("graph.nodes.check_guardrail", dead)
    monkeypatch.setattr("graph.nodes.navigator", spy)

    events = await collect()
    assert not reached["navigator"]
    assert types_of(events).count("error") == 1
    assert "token" not in types_of(events)
    assert steps_at_end(events)["guardrail"] == "failed"


@pytest.mark.asyncio
async def test_judge_failure_keeps_the_answer_but_drops_the_score(
    monkeypatch: pytest.MonkeyPatch, chunks: list[Any]
) -> None:
    """The answer and citations are genuine; only adjudication is missing.

    Confidence must be null rather than the old fabricated 0.5.
    """
    monkeypatch.setattr("graph.nodes.check_guardrail", lambda q: True)
    monkeypatch.setattr("graph.nodes.navigator", lambda q: chunks)
    monkeypatch.setattr(
        "graph.nodes.stream_answer", lambda q, c: iter(["Thiazides ", "are first-line."])
    )

    def dead(q: str, a: str, c: list[Any]) -> Any:
        raise AriaLLMError("judge", "m", "gone", "model_not_found")

    monkeypatch.setattr("graph.nodes.judge_answer", dead)

    events = await collect()
    meta = next(e for e in events if e["type"] == "meta")

    assert meta["confidence"] is None
    assert meta["evidenceTier"] is None, "no tier means no certainty badge"
    assert len(meta["citations"]) == 2, "real citations survive"
    assert "token" in types_of(events), "the grounded answer still streams"
    assert steps_at_end(events)["judge"] == "failed"


@pytest.mark.asyncio
async def test_unparseable_judge_reply_also_yields_no_tier(
    monkeypatch: pytest.MonkeyPatch, chunks: list[Any]
) -> None:
    from agents.judge_agent import Judgment

    monkeypatch.setattr("graph.nodes.check_guardrail", lambda q: True)
    monkeypatch.setattr("graph.nodes.navigator", lambda q: chunks)
    monkeypatch.setattr("graph.nodes.stream_answer", lambda q, c: iter(["Thiazides."]))
    monkeypatch.setattr("graph.nodes.judge_answer", lambda q, a, c: Judgment(None, "unparseable"))

    meta = next(e for e in await collect() if e["type"] == "meta")
    assert meta["confidence"] is None
    assert meta["evidenceTier"] is None


@pytest.mark.asyncio
async def test_out_of_scope_is_not_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A rejected query is a valid outcome, not a failure."""
    monkeypatch.setattr("graph.nodes.check_guardrail", lambda q: False)

    events = await collect("What is the price of Bitcoin?")
    kinds = types_of(events)
    assert "error" not in kinds
    assert "token" in kinds
    assert steps_at_end(events)["navigator"] == "skipped"

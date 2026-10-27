"""
The guardrail: what ARIA answers, what it declines, and how.

The line it draws is intent, not topic. Toxicity, overdose and antidotes
are pharmacy education and must be answered; a message that seeks to harm
the asker or someone else must not be, whatever drug it names. These tests
pin the classification, the two-model cascade behind it, and what each
refusal sends to the browser — never clinical content, never a grade.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

import agents.guardrail_agent as ga
from agents.guardrail_agent import Intent, classify_query, needs_review
from api.server import run_consultation
from llm.config import Role
from llm.errors import AriaLLMError


def route(guardrail: str, safety: str | Exception | None = None) -> Any:
    """A fake invoke_role that answers per role and records who was asked."""
    calls: list[Role] = []

    def fake(role: Role, prompt: str) -> str:
        calls.append(role)
        if role is Role.SAFETY:
            if safety is None:
                raise AssertionError("safety model consulted without cause")
            if isinstance(safety, Exception):
                raise safety
            return safety
        return guardrail

    fake.calls = calls  # type: ignore[attr-defined]
    return fake


# ── Reading the guardrail's reply ──────────────────────────────────────


@pytest.mark.parametrize(
    ("reply", "expected"),
    [
        ("CLINICAL", Intent.CLINICAL),
        ("clinical", Intent.CLINICAL),
        ("Label: CLINICAL.", Intent.CLINICAL),
        ("OUT_OF_SCOPE", Intent.OUT_OF_SCOPE),
        ("out of scope", Intent.OUT_OF_SCOPE),
        # First label wins, as the YES/NO check's first whole word did.
        ("OUT_OF_SCOPE, though it mentions CLINICAL terms", Intent.OUT_OF_SCOPE),
        # Nothing parseable: the guardrail cannot vouch for the query.
        ("I'm not sure what you mean", Intent.OUT_OF_SCOPE),
        ("", Intent.OUT_OF_SCOPE),
    ],
)
def test_reply_parsing(monkeypatch: pytest.MonkeyPatch, reply: str, expected: Intent) -> None:
    monkeypatch.setattr(ga, "invoke_role", route(reply))
    assert classify_query("what is the dose of metformin?") is expected


def test_an_unreachable_guardrail_raises_rather_than_allowing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def down(role: Role, prompt: str) -> str:
        raise AriaLLMError("guardrail", "openai/gpt-oss-20b", "down", "rate_limited")

    monkeypatch.setattr(ga, "invoke_role", down)
    with pytest.raises(AriaLLMError):
        classify_query("what is the dose of metformin?")


# ── The cascade ────────────────────────────────────────────────────────


def test_ordinary_clinical_questions_cost_one_call(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = route("CLINICAL")
    monkeypatch.setattr(ga, "invoke_role", fake)
    assert classify_query("What are the signs of digoxin toxicity?") is Intent.CLINICAL
    assert fake.calls == [Role.GUARDRAIL]


def test_a_flag_confirmed_by_the_reviewer_stands(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = route("SELF_HARM", "SELF_HARM")
    monkeypatch.setattr(ga, "invoke_role", fake)
    assert classify_query("a message the guardrail flagged") is Intent.SELF_HARM
    assert fake.calls == [Role.GUARDRAIL, Role.SAFETY]


def test_the_reviewer_can_clear_an_over_cautious_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    """The cost of refusing a student is real: a confirmed-educational
    question is answered even when the first model flinched."""
    monkeypatch.setattr(ga, "invoke_role", route("SELF_HARM", "EDUCATIONAL"))
    assert classify_query("What is the lethal dose of digoxin?") is Intent.CLINICAL


def test_risk_language_buys_a_review_of_a_clinical_label(monkeypatch: pytest.MonkeyPatch) -> None:
    """The first model's miss is the reviewer's to catch."""
    fake = route("CLINICAL", "HARM_OTHERS")
    monkeypatch.setattr(ga, "invoke_role", fake)
    assert classify_query("which drug would not show up on a test") is Intent.HARM_OTHERS
    assert fake.calls == [Role.GUARDRAIL, Role.SAFETY]


@pytest.mark.parametrize("failure", [AriaLLMError("safety", "m", "x", "rate_limited"), None])
def test_an_unavailable_reviewer_keeps_the_flag(
    monkeypatch: pytest.MonkeyPatch, failure: Exception | None
) -> None:
    """When the two cannot be compared, the cautious reading stands —
    both when the reviewer is down and when it answers nonsense."""
    reviewer = failure if failure is not None else "I cannot determine that."
    monkeypatch.setattr(ga, "invoke_role", route("HARM_OTHERS", reviewer))
    assert classify_query("a message the guardrail flagged") is Intent.HARM_OTHERS


@pytest.mark.parametrize(
    ("query", "first", "expected"),
    [
        ("What are the adverse effects of amiodarone?", Intent.CLINICAL, False),
        ("What is the toxic dose of acetaminophen?", Intent.CLINICAL, False),
        ("What is the lethal dose of digoxin?", Intent.CLINICAL, True),
        ("anything at all", Intent.SELF_HARM, True),
        ("anything at all", Intent.HARM_OTHERS, True),
        ("What is the price of bitcoin?", Intent.OUT_OF_SCOPE, False),
    ],
)
def test_who_gets_a_second_opinion(query: str, first: Intent, expected: bool) -> None:
    assert needs_review(query, first) is expected


# ── What each refusal sends ────────────────────────────────────────────


async def collect(query: str) -> list[dict[str, Any]]:
    return [json.loads(raw[len("data: ") :]) async for raw in run_consultation(query)]


@pytest.mark.asyncio
@pytest.mark.parametrize("intent", [Intent.SELF_HARM, Intent.HARM_OTHERS, Intent.OUT_OF_SCOPE])
async def test_a_refusal_never_reaches_retrieval(
    monkeypatch: pytest.MonkeyPatch, intent: Intent
) -> None:
    def no_retrieval(q: str) -> list[Any]:
        raise AssertionError("a declined question reached the evidence base")

    monkeypatch.setattr("graph.nodes.classify_query", lambda q: intent)
    monkeypatch.setattr("graph.nodes.navigator", no_retrieval)
    events = await collect("a declined question")

    meta = next(e for e in events if e["type"] == "meta")
    assert meta["refusal"] == intent.value
    assert meta["outOfScope"] is True
    assert meta["evidenceTier"] is None and meta["confidence"] is None
    assert meta["citations"] == []
    assert not any(e["type"] == "sources" for e in events)


@pytest.mark.asyncio
async def test_self_harm_gets_support_not_a_lecture(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("graph.nodes.classify_query", lambda q: Intent.SELF_HARM)
    events = await collect("a self-harm message")

    text = "".join(e["chunk"] for e in events if e["type"] == "token")
    assert "14416" in text and "112" in text
    meta = next(e for e in events if e["type"] == "meta")
    assert meta["safety"][0]["kind"] == "support"
    # The trace declines without labelling the reader.
    guard = [e for e in events if e["type"] == "steps"][-1]["steps"][0]
    assert "self" not in guard["detail"].lower()


@pytest.mark.asyncio
async def test_harm_to_others_is_declined_plainly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("graph.nodes.classify_query", lambda q: Intent.HARM_OTHERS)
    events = await collect("a harmful message")

    text = "".join(e["chunk"] for e in events if e["type"] == "token")
    assert text.startswith("I can't help with that.")
    assert next(e for e in events if e["type"] == "meta")["safety"] == []

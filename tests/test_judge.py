"""The Judge never invents a confidence number."""

from __future__ import annotations

from typing import Any

import pytest

from agents.judge_agent import judge_answer
from llm.errors import AriaLLMError


def _patch_judge(monkeypatch: pytest.MonkeyPatch, reply: str) -> None:
    monkeypatch.setattr("agents.judge_agent.invoke_role", lambda role, prompt, **_: reply)


def test_valid_json_is_parsed(monkeypatch: pytest.MonkeyPatch, chunks: list[Any]) -> None:
    _patch_judge(monkeypatch, '{"confidence": 0.91, "reason": "well grounded"}')
    verdict = judge_answer("q", "a", chunks)
    assert verdict.adjudicated
    assert verdict.confidence == 0.91


def test_json_wrapped_in_prose_is_recovered(
    monkeypatch: pytest.MonkeyPatch, chunks: list[Any]
) -> None:
    _patch_judge(monkeypatch, 'Sure!\n```json\n{"confidence": 0.4, "reason": "thin"}\n```')
    assert judge_answer("q", "a", chunks).confidence == 0.4


def test_unparseable_reply_yields_no_score_not_a_placeholder(
    monkeypatch: pytest.MonkeyPatch, chunks: list[Any]
) -> None:
    """Regression: this used to return 0.5, which the UI drew on a real gauge."""
    _patch_judge(monkeypatch, "I think the answer is pretty good overall.")
    verdict = judge_answer("q", "a", chunks)
    assert verdict.confidence is None
    assert not verdict.adjudicated


def test_malformed_json_yields_no_score(monkeypatch: pytest.MonkeyPatch, chunks: list[Any]) -> None:
    _patch_judge(monkeypatch, '{"confidence": "not a number"}')
    assert judge_answer("q", "a", chunks).confidence is None


def test_confidence_is_clamped(monkeypatch: pytest.MonkeyPatch, chunks: list[Any]) -> None:
    _patch_judge(monkeypatch, '{"confidence": 1.7, "reason": "over-eager"}')
    assert judge_answer("q", "a", chunks).confidence == 1.0


def test_provider_failure_propagates(monkeypatch: pytest.MonkeyPatch, chunks: list[Any]) -> None:
    def boom(role: object, prompt: str, **_: object) -> str:
        raise AriaLLMError("judge", "m", "down", "model_not_found")

    monkeypatch.setattr("agents.judge_agent.invoke_role", boom)
    with pytest.raises(AriaLLMError):
        judge_answer("q", "a", chunks)


def test_an_unparseable_reply_is_asked_once_more(
    monkeypatch: pytest.MonkeyPatch, chunks: list[Any]
) -> None:
    replies = iter(["I think it is fine.", '{"confidence": 0.8, "reason": "ok"}'])
    monkeypatch.setattr("agents.judge_agent.invoke_role", lambda role, prompt, **_: next(replies))
    assert judge_answer("q", "a", chunks).confidence == 0.8


def test_the_retry_is_bounded(monkeypatch: pytest.MonkeyPatch, chunks: list[Any]) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        "agents.judge_agent.invoke_role", lambda role, prompt, **_: calls.append(prompt) or "no"
    )
    assert judge_answer("q", "a", chunks).confidence is None
    assert len(calls) == 2


def test_the_judge_asks_for_json_mode(monkeypatch: pytest.MonkeyPatch, chunks: list[Any]) -> None:
    """Constrained decoding, rather than hoping the reply parses."""
    modes: list[bool] = []

    def fake(role: Any, prompt: str, *, json_mode: bool = False) -> str:
        modes.append(json_mode)
        return '{"confidence": 0.9, "reason": "ok"}'

    monkeypatch.setattr("agents.judge_agent.invoke_role", fake)
    judge_answer("q", "a", chunks)
    assert modes == [True]

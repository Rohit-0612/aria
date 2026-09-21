"""The Judge never invents a confidence number."""

from __future__ import annotations

from typing import Any

import pytest

from agents.judge_agent import judge_answer
from llm.errors import AriaLLMError


def _patch_judge(monkeypatch: pytest.MonkeyPatch, reply: str) -> None:
    monkeypatch.setattr("agents.judge_agent.invoke_role", lambda role, prompt: reply)


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
    def boom(role: object, prompt: str) -> str:
        raise AriaLLMError("judge", "m", "down", "model_not_found")

    monkeypatch.setattr("agents.judge_agent.invoke_role", boom)
    with pytest.raises(AriaLLMError):
        judge_answer("q", "a", chunks)

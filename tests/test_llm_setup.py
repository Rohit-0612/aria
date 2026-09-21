"""Retry/fallback behaviour when a primary model is decommissioned."""

from __future__ import annotations

import logging

import pytest

from llm.config import ModelSpec, Role, spec_for
from llm.errors import AriaLLMError
from llm.llm_setup import invoke_role
from tests.test_errors import FakeGroqError


class FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class FakeLLM:
    """Records which model was asked, and fails for a configured set."""

    def __init__(self, model: str, dead: set[str], calls: list[str]) -> None:
        self.model = model
        self._dead = dead
        self._calls = calls

    def invoke(self, prompt: str) -> FakeMessage:
        self._calls.append(self.model)
        if self.model in self._dead:
            raise FakeGroqError("model_not_found")
        return FakeMessage(f"answer from {self.model}")


class Provider:
    """Test double for the whole Groq client layer."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.dead: set[str] = set()


@pytest.fixture
def fake_provider(monkeypatch: pytest.MonkeyPatch) -> Provider:
    """Patch client construction so no test reaches a live provider."""
    provider = Provider()

    def factory(spec: object) -> FakeLLM:
        assert isinstance(spec, ModelSpec)
        return FakeLLM(spec.model, provider.dead, provider.calls)

    monkeypatch.setattr("llm.llm_setup.build_llm", factory)
    return provider


def test_healthy_model_returns_text(fake_provider: Provider) -> None:
    out = invoke_role(Role.GENERATOR, "hi")
    assert out == f"answer from {spec_for(Role.GENERATOR).model}"
    assert len(fake_provider.calls) == 1


def test_dead_primary_falls_back_to_secondary(
    fake_provider: Provider, caplog: pytest.LogCaptureFixture
) -> None:
    primary = spec_for(Role.GENERATOR).model
    fallback = "openai/gpt-oss-20b"
    fake_provider.dead.add(primary)

    with caplog.at_level(logging.WARNING):
        out = invoke_role(Role.GENERATOR, "hi")

    assert out == f"answer from {fallback}"
    assert fake_provider.calls == [primary, fallback]
    assert "falling back" in caplog.text


def test_both_models_dead_raises_rather_than_returning_text(
    fake_provider: Provider,
) -> None:
    fake_provider.dead.update({spec_for(Role.GENERATOR).model, "openai/gpt-oss-20b"})
    with pytest.raises(AriaLLMError) as excinfo:
        invoke_role(Role.GENERATOR, "hi")
    assert excinfo.value.is_dead_model


def test_non_dead_error_does_not_trigger_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A rate limit must not silently downgrade the clinical model."""
    calls: list[str] = []

    class RateLimited:
        def __init__(self, model: str) -> None:
            self.model = model

        def invoke(self, prompt: str) -> FakeMessage:
            calls.append(self.model)
            raise RuntimeError("429 rate limit exceeded")

    monkeypatch.setattr("llm.llm_setup.build_llm", lambda spec: RateLimited(spec.model))
    with pytest.raises(AriaLLMError):
        invoke_role(Role.GENERATOR, "hi")
    assert len(calls) == 1


def test_fallback_skipped_when_it_equals_the_primary(
    fake_provider: Provider, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ARIA_GENERATOR_MODEL", "same/model")
    monkeypatch.setenv("ARIA_FALLBACK_MODEL", "same/model")
    fake_provider.dead.add("same/model")
    with pytest.raises(AriaLLMError):
        invoke_role(Role.GENERATOR, "hi")
    assert fake_provider.calls == ["same/model"]

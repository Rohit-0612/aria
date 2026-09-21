"""Startup validation catches a deprecation before a consultation does."""

from __future__ import annotations

import logging
from typing import Any

import pytest

from llm.errors import AriaPreflightError
from llm.preflight import run_preflight


class FakeModel:
    def __init__(self, model_id: str) -> None:
        self.id = model_id


class FakeModels:
    def __init__(self, ids: list[str]) -> None:
        self._ids = ids

    def list(self) -> Any:
        return type("Page", (), {"data": [FakeModel(i) for i in self._ids]})()


class FakeClient:
    def __init__(self, ids: list[str]) -> None:
        self.models = FakeModels(ids)


LIVE = ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.6-27b"]


def test_all_models_present_is_ok() -> None:
    report = run_preflight(FakeClient(LIVE))
    assert report.ok
    assert not report.missing


def test_missing_model_is_reported_loudly(caplog: pytest.LogCaptureFixture) -> None:
    """The exact scenario that broke ARIA in production."""
    with caplog.at_level(logging.CRITICAL):
        report = run_preflight(FakeClient(["openai/gpt-oss-20b"]))

    assert not report.ok
    assert "openai/gpt-oss-120b" in report.missing
    assert "ARIA PREFLIGHT FAILED" in caplog.text
    # The log must name the fix, not just the symptom.
    assert "ARIA_" in caplog.text


def test_non_strict_mode_still_serves() -> None:
    """A dead primary is survivable — invoke_role falls back."""
    report = run_preflight(FakeClient(["openai/gpt-oss-20b"]))
    assert not report.ok  # returned, not raised


def test_strict_mode_refuses_to_boot(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARIA_PREFLIGHT_STRICT", "1")
    with pytest.raises(AriaPreflightError):
        run_preflight(FakeClient(["openai/gpt-oss-20b"]))


def test_unreachable_provider_does_not_crash_boot(
    caplog: pytest.LogCaptureFixture,
) -> None:
    class Broken:
        @property
        def models(self) -> Any:
            raise ConnectionError("no route to host")

    with caplog.at_level(logging.ERROR):
        report = run_preflight(Broken())  # type: ignore[arg-type]

    assert not report.ok
    assert report.error is not None
    assert "could not reach" in caplog.text


def test_health_payload_shape() -> None:
    payload = run_preflight(FakeClient(LIVE)).as_dict()
    assert payload["ok"] is True
    assert isinstance(payload["checked"], list)

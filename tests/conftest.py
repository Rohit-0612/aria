"""Shared fixtures. No test in this suite may touch a live provider."""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from typing import Any

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Model env vars leak between tests otherwise: llm.config reads them on every
# call by design, so a stray override would silently change later assertions.
_MODEL_VARS = [
    "ARIA_GENERATOR_MODEL",
    "ARIA_JUDGE_MODEL",
    "ARIA_GUARDRAIL_MODEL",
    "ARIA_NAVIGATOR_MODEL",
    "ARIA_EVAL_JUDGE_MODEL",
    "ARIA_SAFETY_MODEL",
    "ARIA_SAFETY_EFFORT",
    "ARIA_FALLBACK_MODEL",
    "ARIA_RERANK_MODEL",
    "ARIA_EMBEDDING_MODEL",
    "ARIA_PREFLIGHT_STRICT",
    "ARIA_GENERATOR_EFFORT",
    "ARIA_JUDGE_EFFORT",
    "ARIA_GUARDRAIL_EFFORT",
    "ARIA_NAVIGATOR_EFFORT",
    "ARIA_EVAL_JUDGE_EFFORT",
]


@pytest.fixture(autouse=True)
def clean_model_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for var in _MODEL_VARS:
        monkeypatch.delenv(var, raising=False)
    # The outline planner and the Gemini generator both call a live model
    # the moment they are reachable. Off by default here; tests of those
    # paths switch them on explicitly, with the provider faked.
    monkeypatch.setenv("ARIA_FACET_RETRIEVAL", "0")
    monkeypatch.delenv("ARIA_GENERATOR_CASCADE", raising=False)
    # Set empty rather than deleted: `load_dotenv()` runs when llm_setup is
    # first imported and would otherwise put the real key back mid-test. It
    # never overrides a variable that already exists, even an empty one.
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("GOOGLE_API_KEY", "")
    yield


def as_retrieval(fake: Any) -> Any:
    """Adapt a fake `navigator(query) -> chunks` to `navigate(query) -> Retrieval`.

    The node now receives the passages together with the teaching outline;
    the fakes in these tests only care about the passages, so they keep
    returning (or raising) exactly what they did, wrapped.
    """
    from agents.navigator_agent import Retrieval

    return lambda q: Retrieval(chunks=fake(q))


class FakeDoc:
    """Minimal stand-in for a LangChain Document."""

    def __init__(self, text: str, metadata: dict[str, Any] | None = None) -> None:
        self.page_content = text
        self.metadata = metadata or {}


@pytest.fixture
def chunks() -> list[Any]:
    return [
        FakeDoc(
            "Thiazide diuretics are first-line for hypertension.",
            {"page": 412, "book": "dipiro", "relevance_score": 0.91},
        ),
        FakeDoc(
            "ACE inhibitors reduce mortality post-MI.",
            {"page": 88, "book": "rxprep", "relevance_score": 0.77},
        ),
    ]

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
    "ARIA_FALLBACK_MODEL",
    "ARIA_RERANK_MODEL",
    "ARIA_EMBEDDING_MODEL",
    "ARIA_PREFLIGHT_STRICT",
]


@pytest.fixture(autouse=True)
def clean_model_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for var in _MODEL_VARS:
        monkeypatch.delenv(var, raising=False)
    yield


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

"""
The shared state threaded through the ARIA graph.

`failure` is the field that keeps a dependency error from ever being
mistaken for an answer. When it is set, `answer` is guaranteed to be empty
and every downstream consumer — the graph's routing, the API layer, the UI —
treats the turn as failed rather than rendering it as clinical content.

It records a failed *model* call and a failed *retrieval* identically,
because the routing consequence is the same; `source` and `code` preserve
which dependency actually broke.
"""

from __future__ import annotations

from typing import Any, TypedDict

from llm.errors import AriaStageError

__all__ = ["AriaFailure", "AriaState", "initial_state", "record_failure"]


class AriaFailure(TypedDict):
    """A stage failure, in a form the API layer can serialise directly."""

    stage: str
    #: The dependency that failed — a model ID, or the evidence collection.
    source: str
    code: str | None
    message: str


class AriaState(TypedDict):
    """State object for the compiled LangGraph app."""

    query: str
    chunks: list[Any]
    answer: str
    is_medical: bool
    #: None means "not adjudicated" — never substitute a placeholder number.
    confidence: float | None
    #: Set only when a model call or retrieval failed. Mutually exclusive
    #: with a usable `answer`.
    failure: AriaFailure | None
    #: True when the answer is genuine but the Judge could not score it.
    judge_failed: bool


def initial_state(question: str) -> AriaState:
    """A clean state for one consultation."""
    return AriaState(
        query=question,
        chunks=[],
        answer="",
        is_medical=False,
        confidence=None,
        failure=None,
        judge_failed=False,
    )


def record_failure(state: AriaState, exc: AriaStageError) -> AriaState:
    """Mark the turn as failed and guarantee no answer-shaped text survives."""
    state["failure"] = AriaFailure(
        stage=exc.stage,
        source=exc.source,
        code=exc.code,
        message=exc.public_message(),
    )
    state["answer"] = ""
    state["confidence"] = None
    return state

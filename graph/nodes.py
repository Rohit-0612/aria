"""
LangGraph node functions.

Every node that touches an external dependency converts a failure into an
explicit `failure` entry on the state and stops the pipeline. No node ever
writes an error message into `answer` — that field is reserved for grounded
content, and the graph's routing depends on telling the two apart.

Nodes also narrate themselves. Each one announces when it becomes active
and how it finished, through LangGraph's custom stream channel, so the
agent trace the reader watches is emitted by the pipeline that actually ran
rather than reconstructed by the transport from its own copy of the routing
rules. Outside a streaming run the writer is a no-op, so the same nodes
serve the eval suite and the CLI unchanged.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

from langgraph.config import get_stream_writer

from agents.guardrail_agent import check_guardrail
from agents.judge_agent import judge_answer
from agents.navigator_agent import navigator
from graph.state import AriaState, record_failure
from llm.errors import AriaStageError, wrap_provider_error, wrap_retrieval_error
from llm.generator import stream_answer

logger = logging.getLogger(__name__)

__all__ = [
    "REJECTION_MESSAGE",
    "generator_node",
    "guardrail_node",
    "judge_node",
    "navigator_node",
    "reject_node",
]

REJECTION_MESSAGE = (
    "That falls outside my scope. I'm **ARIA**, a clinical pharmacotherapy "
    "assistant — I can help with drug selection, dosing, monitoring, "
    "interactions, and the evidence behind therapeutic decisions, grounded "
    "in *DiPiro's Pharmacotherapy*."
)


def _writer() -> Callable[[dict[str, Any]], None]:
    """The stream writer, or a no-op when not streaming."""
    try:
        return get_stream_writer()
    except Exception:  # noqa: BLE001 - absence of a stream is not an error
        return lambda _: None


def _start(step: str, detail: str) -> tuple[Callable[[dict[str, Any]], None], float]:
    write = _writer()
    write({"kind": "step", "id": step, "status": "active", "detail": detail})
    return write, time.time()


def _done(
    write: Callable[[dict[str, Any]], None],
    step: str,
    t0: float,
    *,
    detail: str,
    metric: str | None = None,
) -> None:
    write(
        {
            "kind": "step",
            "id": step,
            "status": "done",
            "detail": detail,
            "metric": metric,
            "durationMs": int((time.time() - t0) * 1000),
        }
    )


def _failed(
    write: Callable[[dict[str, Any]], None],
    step: str,
    t0: float,
    exc: AriaStageError,
) -> None:
    logger.error("consultation failed at %s: %s", step, exc)
    write(
        {
            "kind": "step",
            "id": step,
            "status": "failed",
            "detail": "Failed — no answer produced",
            "metric": None,
            "durationMs": int((time.time() - t0) * 1000),
        }
    )


def guardrail_node(state: AriaState) -> AriaState:
    write, t0 = _start("guardrail", "Confirming the query is in clinical scope")
    try:
        state["is_medical"] = check_guardrail(state["query"])
    except Exception as raw:  # noqa: BLE001 - normalised on the next line
        exc = wrap_provider_error(raw, "guardrail", "guardrail model")
        # Deliberately NOT defaulting to in-scope: an unreachable guardrail
        # cannot vouch for the query, so the consultation stops here.
        record_failure(state, exc)
        _failed(write, "guardrail", t0, exc)
        return state

    in_scope = state["is_medical"]
    _done(
        write,
        "guardrail",
        t0,
        detail=(
            "Clinical pharmacotherapy query" if in_scope else "Query is outside clinical scope"
        ),
        metric="medical · in scope" if in_scope else "out of scope",
    )
    return state


def navigator_node(state: AriaState) -> AriaState:
    write, t0 = _start("navigator", "Retrieving & reranking source passages")
    try:
        state["chunks"] = navigator(state["query"])
    except Exception as raw:  # noqa: BLE001 - normalised on the next line
        # Bare exceptions are wrapped as *retrieval* failures rather than
        # escaping the graph: anything unforeseen here is still the evidence
        # base failing, and must reach the reader as that.
        exc = wrap_retrieval_error(raw, "navigator")
        # Catches both kinds: the query-rewrite model and the vector store.
        # An empty retrieval arrives here too — never carried on as "no
        # chunks", which would let the generator answer from memory.
        record_failure(state, exc)
        _failed(write, "navigator", t0, exc)
        return state

    _done(
        write,
        "navigator",
        t0,
        detail="Top passages selected by relevance",
        metric=f"{len(state['chunks'])} passages kept",
    )
    return state


def generator_node(state: AriaState) -> AriaState:
    """Write the answer, streaming it as it is produced.

    Fragments are published explicitly on the custom channel rather than
    being picked up from LangGraph's `messages` channel. That channel
    carries every model call in the graph, so using it would mean the
    transport filtering the guardrail, the query rewrite and the judge out
    of the reply by node name — and would emit nothing at all if the
    generator were ever changed to produce text without calling a model.
    Publishing here makes the reply prose an explicit output of this node,
    which is what it is.

    The fragments are also accumulated, so the Judge and the eval suite see
    a whole answer. A mid-stream failure discards the partial text — it is
    not an answer, and `record_failure` guarantees it cannot be treated as
    one downstream.
    """
    write, t0 = _start("generator", "Synthesizing a grounded answer")
    parts: list[str] = []
    try:
        for piece in stream_answer(state["query"], state["chunks"]):
            parts.append(piece)
            write({"kind": "token", "text": piece})
    except Exception as raw:  # noqa: BLE001 - normalised on the next line
        exc = wrap_provider_error(raw, "generator", "generator model")
        record_failure(state, exc)
        _failed(write, "generator", t0, exc)
        return state

    state["answer"] = "".join(parts)
    _done(
        write,
        "generator",
        t0,
        detail="Answer grounded in retrieved passages",
        metric=f"{len(state['chunks'])} sources cited",
    )
    return state


def judge_node(state: AriaState) -> AriaState:
    write, t0 = _start("judge", "Scoring faithfulness & evidence strength")
    try:
        judgment = judge_answer(state["query"], state["answer"], state["chunks"])
    except Exception as raw:  # noqa: BLE001 - normalised on the next line
        exc = wrap_provider_error(raw, "judge", "judge model")
        # The answer itself is real and grounded; only adjudication failed.
        # Leave `answer` intact, mark it unadjudicated, and let the caller
        # present it without a fabricated score.
        logger.warning("judge unavailable (%s) — answer left unadjudicated", exc.code)
        state["confidence"] = None
        state["judge_failed"] = True
        write(
            {
                "kind": "step",
                "id": "judge",
                "status": "failed",
                "detail": "Judge unavailable — answer not scored",
                "metric": "not adjudicated",
                "durationMs": int((time.time() - t0) * 1000),
            }
        )
        return state

    state["confidence"] = judgment.confidence
    state["judge_failed"] = False

    if judgment.confidence is None:
        write(
            {
                "kind": "step",
                "id": "judge",
                "status": "failed",
                "detail": "Judge returned no usable score",
                "metric": "not adjudicated",
                "durationMs": int((time.time() - t0) * 1000),
            }
        )
        return state

    _done(
        write,
        "judge",
        t0,
        detail="Answer scored for faithfulness to cited sources",
        metric=f"{round(judgment.confidence * 100)}% confidence",
    )
    return state


def reject_node(state: AriaState) -> AriaState:
    """Decline an out-of-scope query.

    The refusal is emitted on the same token channel as a generated answer
    because that is what it is to the reader — prose in the reply. It is not
    grounded content, so nothing downstream attaches citations or a score.
    """
    write = _writer()
    state["answer"] = REJECTION_MESSAGE
    write({"kind": "token", "text": REJECTION_MESSAGE})
    for step in ("navigator", "generator", "judge"):
        write({"kind": "step", "id": step, "status": "skipped", "detail": "Skipped — out of scope"})
    return state

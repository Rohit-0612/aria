"""
The ARIA graph: guardrail -> navigator -> generator -> judge.

This is the pipeline. There is no second copy of it: the API server drives
this graph rather than re-running the same four agents in its own order,
because for a while there were two implementations and they had already
drifted apart — one grew a retry loop and a `judge_failed` flag the other
never had. A bug fixed in one was not fixed in the other.

Routing is failure-aware at every hop. Once `state["failure"]` is set the
graph goes straight to END, so a dead dependency can never be carried
forward into retrieval, generation or scoring.

On the absent retry loop
------------------------
The judge used to be able to send a low-confidence answer back to the
generator, up to three times. It could never have helped: the generator
runs at temperature 0 on an unchanged prompt, so every retry regenerated
the same answer, scored it the same way, and returned it anyway after
burning three times the tokens and latency. Rewriting it to feed the
judge's critique back would be a real feature — and a different one, whose
output the reader would watch being replaced mid-answer. Removed rather
than left in as decoration.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

from langgraph.graph import END, START, StateGraph

from graph.nodes import (
    generator_node,
    guardrail_node,
    judge_node,
    navigator_node,
    reject_node,
)
from graph.state import AriaState, initial_state

logger = logging.getLogger(__name__)

__all__ = ["AriaState", "ask_aria", "build_aria", "run_aria", "stream_aria"]


def guardrail_decision(state: AriaState) -> str:
    if state["failure"] is not None:
        return "fail"
    return "navigator" if state["is_medical"] else "reject"


def navigator_decision(state: AriaState) -> str:
    return "fail" if state["failure"] is not None else "generator"


def generator_decision(state: AriaState) -> str:
    return "fail" if state["failure"] is not None else "judge"


def build_aria() -> Any:
    graph: StateGraph[AriaState, Any, Any, Any] = StateGraph(AriaState)

    graph.add_node("guardrail", guardrail_node)
    graph.add_node("navigator", navigator_node)
    graph.add_node("generator", generator_node)
    graph.add_node("judge", judge_node)
    graph.add_node("reject", reject_node)

    graph.add_edge(START, "guardrail")

    graph.add_conditional_edges(
        "guardrail",
        guardrail_decision,
        {"navigator": "navigator", "reject": "reject", "fail": END},
    )
    graph.add_conditional_edges(
        "navigator",
        navigator_decision,
        {"generator": "generator", "fail": END},
    )
    graph.add_conditional_edges(
        "generator",
        generator_decision,
        {"judge": "judge", "fail": END},
    )
    graph.add_edge("judge", END)
    graph.add_edge("reject", END)

    return graph.compile()


# Compiled once and reused across calls
_app: Any | None = None


def _get_app() -> Any:
    global _app
    if _app is None:
        _app = build_aria()
    return _app


async def stream_aria(question: str) -> AsyncIterator[dict[str, Any]]:
    """Run one consultation, yielding its progress as it happens.

    This is the serving path. It emits three kinds of event, and the caller
    needs no knowledge of the pipeline to render them:

        {"type": "step",  ...}       an agent step changed status
        {"type": "token", "text": s} a fragment of reply prose
        {"type": "final", "state": AriaState}  the finished state

    Reply prose comes from whichever node produced it — the generator
    streaming a grounded answer, or `reject_node` declining an out-of-scope
    query — and both publish it explicitly. LangGraph's `messages` channel
    is deliberately not used: it carries every model call in the graph, so
    the guardrail, the query rewrite and the judge would all have to be
    filtered back out of the reader's reply by node name.
    """
    final: AriaState | None = None

    async for mode, payload in _get_app().astream(
        initial_state(question),
        stream_mode=["custom", "values"],
    ):
        if mode == "custom":
            kind = payload.get("kind")
            if kind == "step":
                yield {"type": "step", **{k: v for k, v in payload.items() if k != "kind"}}
            elif kind == "token":
                yield {"type": "token", "text": payload["text"]}

        elif mode == "values":
            final = payload

    if final is None:  # pragma: no cover - astream always emits values
        final = initial_state(question)
    yield {"type": "final", "state": final}


def run_aria(question: str) -> AriaState:
    """Run one consultation and return the full final state.

    The batch form, for callers with nothing to stream to. Prefer this over
    `ask_aria` when the caller needs to distinguish an answer from a
    failure — which is every caller that renders to a user.
    """
    final: AriaState = _get_app().invoke(initial_state(question))
    return final


def ask_aria(question: str) -> str:
    """Convenience wrapper returning just the answer text.

    Raises:
        AriaStageError: if the consultation failed. It deliberately does not
            return the error as a string — that is the bug this refactor
            exists to remove.
    """
    from llm.errors import AriaStageError

    final = run_aria(question)
    failure = final["failure"]
    if failure is not None:
        raise AriaStageError(
            stage=failure["stage"],
            source=failure["source"],
            message=failure["message"],
            code=failure["code"],
        )
    return final["answer"]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    for label, probe in [
        ("Medical Query", "What is the treatment for hypertension?"),
        ("Non-Medical Query", "What is the price of Bitcoin?"),
    ]:
        print("=" * 60)
        print(f"TEST: {label}")
        print("=" * 60)
        result = run_aria(probe)
        if result["failure"] is not None:
            print(f"FAILED: {result['failure']['message']}")
        else:
            print(f"confidence: {result['confidence']}")
            print(result["answer"])
        print()

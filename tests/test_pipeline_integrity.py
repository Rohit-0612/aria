"""
One pipeline, streamed honestly, and bounded.

These cover the refactor that removed the second copy of the pipeline from
the API layer, replaced the artificial token drip with real streaming, and
put limits on a public endpoint that spends money on every call.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

import api.server as server
from agents.judge_agent import Judgment
from api.server import run_consultation


async def collect(
    query: str = "What is first-line therapy for hypertension?",
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    async for raw in run_consultation(query):
        events.append(json.loads(raw[len("data: ") :]))
    return events


def types_of(events: list[dict[str, Any]]) -> list[str]:
    return [e["type"] for e in events]


@pytest.fixture
def working_pipeline(monkeypatch: pytest.MonkeyPatch, chunks: list[Any]) -> list[str]:
    """A graph whose generator yields several distinct fragments."""
    fragments = ["Thiazide ", "diuretics ", "are ", "first-line."]
    monkeypatch.setattr("graph.nodes.check_guardrail", lambda q: True)
    monkeypatch.setattr("graph.nodes.navigator", lambda q: chunks)
    monkeypatch.setattr("graph.nodes.stream_answer", lambda q, c: iter(fragments))
    monkeypatch.setattr("graph.nodes.judge_answer", lambda q, a, c: Judgment(0.88, "grounded"))
    return fragments


# ── One pipeline ───────────────────────────────────────────────────────


def test_the_api_layer_owns_no_pipeline() -> None:
    """The server must not import the agents and re-orchestrate them.

    It did, while the compiled graph sat unused, and the two copies drifted:
    one grew a retry loop and a judge_failed flag the other never had. This
    pins the server to transport only.
    """
    for agent in ("check_guardrail", "navigator", "generate_answer", "judge_answer"):
        assert not hasattr(server, agent), (
            f"api.server re-imported {agent!r} — the pipeline belongs to graph.aria_graph"
        )


def test_the_graph_has_no_retry_loop() -> None:
    """The judge cannot send the answer back to the generator.

    The loop could never work: temperature 0 on an unchanged prompt returns
    the same answer, so it only spent tokens and latency before giving up.
    """
    from graph.aria_graph import build_aria
    from graph.state import initial_state

    assert "retry_count" not in initial_state("x")
    edges = build_aria().get_graph().edges
    assert not any(e.source == "judge" and e.target == "generator" for e in edges)


# ── Real streaming ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_prose_streams_in_fragments_not_one_block(working_pipeline: list[str]) -> None:
    """Each fragment the generator yields reaches the browser as it arrives.

    The old transport waited for the whole answer, then re-split it and
    dripped it back out on a 14ms timer — the reader waited for generation
    AND for the replay.
    """
    events = await collect()
    tokens = [e["chunk"] for e in events if e["type"] == "token"]

    assert tokens == working_pipeline, "fragments must pass through unaltered and in order"
    assert len(tokens) > 1, "a single block would mean the stream was buffered"


@pytest.mark.asyncio
async def test_meta_arrives_after_the_prose(working_pipeline: list[str]) -> None:
    """The Judge can only score a finished answer, so the gauge comes last.

    The UI renders the gauge and the source rail only on a completed turn,
    so nothing is ever shown with an ungraded score attached.
    """
    kinds = types_of(await collect())
    assert kinds.index("meta") > max(i for i, k in enumerate(kinds) if k == "token")
    assert kinds[-1] == "done"


@pytest.mark.asyncio
async def test_no_artificial_delay_between_tokens(
    working_pipeline: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nothing in the transport sleeps between fragments."""
    slept: list[float] = []

    async def spy(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr(server.asyncio, "sleep", spy)
    await collect()
    assert not slept, f"transport slept {slept} between events"


# ── Limits on a public, paid endpoint ──────────────────────────────────


def test_rate_limit_allows_the_budget_then_refuses(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "_RATE_LIMIT", 3)
    monkeypatch.setattr(server, "_RATE_WINDOW", 60.0)
    monkeypatch.setattr(server, "_hits", server.defaultdict(server.deque))

    assert [server.over_rate_limit("1.2.3.4", now=1000.0) for _ in range(3)] == [False] * 3
    assert server.over_rate_limit("1.2.3.4", now=1000.0) is True


def test_rate_limit_is_per_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "_RATE_LIMIT", 1)
    monkeypatch.setattr(server, "_hits", server.defaultdict(server.deque))

    assert server.over_rate_limit("1.1.1.1", now=1.0) is False
    assert server.over_rate_limit("1.1.1.1", now=1.0) is True
    assert server.over_rate_limit("2.2.2.2", now=1.0) is False, "one client must not block another"


def test_rate_limit_window_rolls_forward(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "_RATE_LIMIT", 1)
    monkeypatch.setattr(server, "_RATE_WINDOW", 60.0)
    monkeypatch.setattr(server, "_hits", server.defaultdict(server.deque))

    assert server.over_rate_limit("1.1.1.1", now=0.0) is False
    assert server.over_rate_limit("1.1.1.1", now=30.0) is True
    assert server.over_rate_limit("1.1.1.1", now=61.0) is False, "the window must expire"


def test_rate_limiting_can_be_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "_RATE_LIMIT", 0)
    assert all(not server.over_rate_limit("1.1.1.1", now=1.0) for _ in range(50))


def test_forwarded_client_is_preferred_behind_the_proxy() -> None:
    request = SimpleNamespace(
        headers={"x-forwarded-for": "203.0.113.9, 10.0.0.1"},
        client=None,
    )
    assert server.client_key(request) == "203.0.113.9"


def test_socket_client_is_used_when_not_proxied() -> None:
    request = SimpleNamespace(headers={}, client=SimpleNamespace(host="198.51.100.7"))
    assert server.client_key(request) == "198.51.100.7"

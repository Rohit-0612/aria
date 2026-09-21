"""
Retrieval failures — the outage this suite was written after.

ARIA's Qdrant cluster stopped existing. Three separate defects turned that
into a confusing outage instead of an obvious one, and each is pinned here:

  1. the failure was reported as a *language model* failure, sending the
     diagnosis to the one dependency that was still healthy;
  2. an empty retrieval was not a failure at all, so the generator could be
     asked to answer with no evidence;
  3. /api/health reported "ok" throughout, because it only ever checked the
     model provider.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from api.server import run_consultation
from llm.errors import (
    EMPTY_RETRIEVAL_CODE,
    AriaLLMError,
    AriaRetrievalError,
    AriaStageError,
    wrap_provider_error,
    wrap_retrieval_error,
)


async def collect(
    query: str = "What is first-line therapy for hypertension?",
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    async for raw in run_consultation(query):
        events.append(json.loads(raw[len("data: ") :]))
    return events


def types_of(events: list[dict[str, Any]]) -> list[str]:
    return [e["type"] for e in events]


# ── The taxonomy itself ────────────────────────────────────────────────


def test_retrieval_error_does_not_blame_the_language_model() -> None:
    """THE misdiagnosis test.

    A dead vector store used to announce itself as "failed to reach the
    language model", which is how an outage caused by a deleted Qdrant
    cluster got investigated as an LLM billing problem.
    """
    err = wrap_retrieval_error(ConnectionResetError(54, "Connection reset by peer"))
    msg = err.public_message()

    assert isinstance(err, AriaRetrievalError)
    assert "language model" not in msg
    assert "reference library" in msg
    assert "No clinical content was generated." in msg
    # Still never answer-shaped.
    assert "Connection reset" not in msg


def test_empty_retrieval_has_its_own_message() -> None:
    """Reachable-but-empty is a different operator problem from unreachable."""
    empty = AriaRetrievalError("navigator", "aria_medical", "nothing", EMPTY_RETRIEVAL_CODE)
    assert empty.is_empty
    assert "no passages" in empty.public_message()

    down = AriaRetrievalError("navigator", "aria_medical", "boom", "retrieval_unavailable")
    assert not down.is_empty
    assert "unreachable" in down.public_message()


def test_llm_error_messaging_is_unchanged() -> None:
    """The provider-failure wording must survive the new hierarchy."""
    err = wrap_provider_error(RuntimeError("rate limited"), "generator", "openai/gpt-oss-120b")
    assert isinstance(err, AriaLLMError)
    assert "language model" in err.public_message()
    assert err.model == "openai/gpt-oss-120b" == err.source


def test_wrapping_preserves_an_existing_retrieval_error() -> None:
    """A retrieval error passing through a provider handler keeps its identity."""
    original = AriaRetrievalError("navigator", "aria_medical", "gone", "retrieval_unavailable")
    assert wrap_provider_error(original, "navigator", "some-model") is original
    assert isinstance(original, AriaStageError)


# ── The generator must never answer ungrounded ─────────────────────────


def test_generator_refuses_to_answer_with_no_passages() -> None:
    """The lock on the core claim: no passages, no answer.

    Previously an empty chunk list produced an empty CONTEXT block and the
    model answered from its own memory — output that the UI then dressed in
    citations furniture and a confidence gauge.
    """
    from llm.generator import generate_answer

    with pytest.raises(AriaRetrievalError) as caught:
        generate_answer("What is the dose of warfarin?", [])
    assert caught.value.code == EMPTY_RETRIEVAL_CODE


def test_navigator_raises_rather_than_returning_no_chunks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import agents.navigator_agent as nav

    class EmptyRetriever:
        def invoke(self, query: str) -> list[Any]:
            return []

    monkeypatch.setattr(nav, "_retriever", EmptyRetriever())
    monkeypatch.setattr(nav, "optimize_query", lambda q: q)

    with pytest.raises(AriaRetrievalError) as caught:
        nav.navigator("What is first-line therapy for hypertension?")
    assert caught.value.code == EMPTY_RETRIEVAL_CODE


# ── End to end through the SSE stream ──────────────────────────────────


@pytest.mark.asyncio
async def test_dead_vector_store_streams_a_retrieval_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The exact production failure, end to end."""

    def dead(q: str) -> list[Any]:
        raise ConnectionResetError(54, "Connection reset by peer")

    monkeypatch.setattr("graph.nodes.check_guardrail", lambda q: True)
    monkeypatch.setattr("graph.nodes.navigator", dead)

    events = await collect()
    kinds = types_of(events)

    assert "token" not in kinds, "a failure must never travel as answer prose"
    assert "meta" not in kinds, "a failure must never carry badge metadata"
    assert kinds.count("error") == 1

    err = next(e for e in events if e["type"] == "error")
    assert err["stage"] == "navigator"
    assert err["code"] == "retrieval_unavailable"
    assert "language model" not in err["message"]
    assert "reference library" in err["message"]


@pytest.mark.asyncio
async def test_empty_retrieval_never_reaches_the_reader_as_an_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An un-restored (empty) collection must fail, not produce prose."""
    monkeypatch.setattr("graph.nodes.check_guardrail", lambda q: True)
    monkeypatch.setattr("graph.nodes.navigator", lambda q: [])

    events = await collect()
    kinds = types_of(events)

    assert "token" not in kinds
    assert "meta" not in kinds
    err = next(e for e in events if e["type"] == "error")
    assert err["code"] == EMPTY_RETRIEVAL_CODE


# ── The health check must not claim "ok" through an outage ─────────────


class FakeQdrant:
    """Stands in for QdrantClient with a scripted collection state."""

    def __init__(self, *, exists: bool = True, points: int = 31228, raises: bool = False) -> None:
        self._exists = exists
        self._points = points
        self._raises = raises

    def collection_exists(self, name: str) -> bool:
        if self._raises:
            raise ConnectionResetError(54, "Connection reset by peer")
        return self._exists

    def get_collection(self, name: str) -> Any:
        vectors = type("V", (), {"size": 384})()
        params = type("P", (), {"vectors": vectors})()
        config = type("C", (), {"params": params})()
        return type("Info", (), {"points_count": self._points, "config": config})()


def test_store_probe_reports_an_unreachable_cluster() -> None:
    from vectorstore.qdrant_store import check_store

    report = check_store(FakeQdrant(raises=True))
    assert not report.ok
    assert not report.reachable
    assert report.error is not None


def test_store_probe_reports_a_missing_collection() -> None:
    from vectorstore.qdrant_store import check_store

    report = check_store(FakeQdrant(exists=False))
    assert not report.ok
    assert report.reachable, "the cluster answered — only the collection is gone"
    assert "does not exist" in (report.error or "")


def test_an_empty_collection_is_not_healthy() -> None:
    """A store with no vectors cannot ground an answer, so it is an outage.

    This is the state the Space would be left in by a half-finished restore.
    """
    from vectorstore.qdrant_store import check_store

    assert not check_store(FakeQdrant(points=0)).ok


def test_a_populated_collection_is_healthy() -> None:
    from vectorstore.qdrant_store import check_store

    report = check_store(FakeQdrant(points=31228))
    assert report.ok
    assert report.points == 31228
    assert report.vector_size == 384

"""
ARIA bridge server.
------------------------------------------------------------------
Transport only. The pipeline lives in `graph.aria_graph`; this module drives
that graph and translates its events into Server-Sent Events whose shape
matches `web/src/lib/client.ts` (ConsultationEvent).

It deliberately holds no pipeline knowledge — no agent order, no routing, no
retry policy. It used to: `run_consultation` called the four agents itself,
in its own order, with its own failure handling, while the compiled graph sat
unused. Two implementations of one pipeline had already drifted, and a fix
applied to one silently missed the other.

Event contract, and the reason it looks like this:

  steps  — agent trace; a step may end `done`, `skipped` or `failed`
  meta   — evidence tier, confidence, citations. Emitted ONLY when a real
           grounded answer exists, and emitted AFTER the prose: the answer
           streams as it is written, and the Judge can only score it once it
           is finished. The UI renders the gauge and the source rail only on
           a completed turn, so nothing is shown ungraded.
           `confidence: null` means the answer is real but was not
           adjudicated.
  token  — a fragment of reply prose, and nothing else, forwarded as the
           model writes it. An exception message must never travel on this
           channel: the UI renders tokens as the assistant's reply and
           decorates them with an evidence tier, so an error sent as a token
           is presented to a clinician with the full authority of a cited
           answer.
  error  — a failure. Terminal, carries no confidence and no citations.
  done   — end of turn.

Run from the project root:
    aria_env/bin/uvicorn api.server:app --port 8000
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sys
import threading
import time
from collections import defaultdict, deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

# Allow running as `python api/server.py` as well as `uvicorn api.server:app`
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from graph.aria_graph import stream_aria
from graph.state import AriaFailure
from llm.errors import AriaStageError, wrap_provider_error
from llm.preflight import PreflightReport, run_preflight
from vectorstore.qdrant_store import StoreReport, check_store

logging.basicConfig(
    level=os.getenv("ARIA_LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("aria.api")

#: Results of the boot-time checks, exposed on /api/health.
_preflight: PreflightReport = PreflightReport()
_store: StoreReport = StoreReport(collection="(unchecked)")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Validate every hard dependency before serving a single request.

    Both dependencies are checked, not just the model provider. Reporting
    "ok" while the evidence base was gone is what let a total outage look
    healthy from the outside for as long as it did.
    """
    global _preflight, _store
    _preflight, _store = await asyncio.gather(
        asyncio.to_thread(run_preflight),
        asyncio.to_thread(check_store),
    )
    yield


app = FastAPI(title="ARIA Bridge", lifespan=lifespan)

# In production the API and the built UI are served from the same origin, so
# no cross-origin access is needed at all. The dev server (vite, port 5183)
# proxies /api, so it is same-origin too. Extra origins can be allowed
# explicitly via ARIA_CORS_ORIGINS rather than opening the API to every site.
_CORS_ORIGINS = [o.strip() for o in os.getenv("ARIA_CORS_ORIGINS", "").split(",") if o.strip()]
if _CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_CORS_ORIGINS,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )


class ConsultRequest(BaseModel):
    query: str


# ── Rate limiting ──────────────────────────────────────────────────────
# /api/consult is public and every call spends real money and quota: four
# model calls plus a Cohere rerank. Groq's on-demand tier also caps the
# generator at 8000 tokens per minute, so a handful of simultaneous readers
# can push each other into 429s and turn a working demo into a broken one.
#
# Two limits, doing different jobs. The per-client window stops one visitor
# monopolising the Space; the global semaphore bounds total concurrency so
# the TPM ceiling is respected no matter how many distinct clients arrive.
# Both are in-process, which is exactly right for a single-container Space
# and would need replacing with something shared if it were ever replicated.
_RATE_LIMIT = int(os.getenv("ARIA_RATE_LIMIT", "10"))
_RATE_WINDOW = float(os.getenv("ARIA_RATE_WINDOW_SECONDS", "60"))
_MAX_CONCURRENT = int(os.getenv("ARIA_MAX_CONCURRENT", "4"))

_hits: dict[str, deque[float]] = defaultdict(deque)
_hits_lock = threading.Lock()
_consult_slots = asyncio.Semaphore(_MAX_CONCURRENT)


def client_key(request: Request) -> str:
    """Identify the caller for rate limiting.

    Behind the Space's proxy the socket address is the proxy, so the
    forwarded client is used when present. It is spoofable, which is why the
    global concurrency bound exists as well — that one cannot be evaded by
    forging a header.
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def over_rate_limit(key: str, now: float | None = None) -> bool:
    """True when `key` has already used its allowance for the window."""
    if _RATE_LIMIT <= 0:
        return False
    moment = time.time() if now is None else now
    with _hits_lock:
        seen = _hits[key]
        while seen and moment - seen[0] > _RATE_WINDOW:
            seen.popleft()
        if len(seen) >= _RATE_LIMIT:
            return True
        seen.append(moment)
        return False


def sse(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event)}\n\n"


def base_steps() -> list[dict[str, Any]]:
    return [
        {
            "id": "guardrail",
            "label": "Guardrail",
            "detail": "Confirming the query is in clinical scope",
            "status": "pending",
        },
        {
            "id": "navigator",
            "label": "Navigator",
            "detail": "Retrieving & reranking DiPiro passages",
            "status": "pending",
        },
        {
            "id": "generator",
            "label": "Generator",
            "detail": "Synthesizing a grounded answer",
            "status": "pending",
        },
        {
            "id": "judge",
            "label": "Judge",
            "detail": "Scoring faithfulness & evidence strength",
            "status": "pending",
        },
    ]


def tier_from_confidence(c: float) -> str:
    if c >= 0.8:
        return "strong"
    if c >= 0.6:
        return "moderate"
    return "limited"


def tier_from_relevance(r: Any) -> str:
    try:
        value = float(r)
    except (TypeError, ValueError):
        return "moderate"
    if value >= 0.75:
        return "strong"
    if value >= 0.5:
        return "moderate"
    return "limited"


# How each source book is cited and labelled in the UI.
BOOKS: dict[str, dict[str, str]] = {
    "dipiro": {
        "source": "DiPiro's Pharmacotherapy",
        "section": "A Pathophysiologic Approach, 12e",
    },
    "rxprep": {
        "source": "RxPrep NAPLEX Course Book (2025)",
        "section": "UWorld · NAPLEX review",
    },
}


def build_citations(chunks: list[Any]) -> list[dict[str, Any]]:
    cites: list[dict[str, Any]] = []
    for i, doc in enumerate(chunks):
        meta = getattr(doc, "metadata", {}) or {}
        rel = meta.get("relevance_score", meta.get("score"))
        snippet = re.sub(r"\s+", " ", (getattr(doc, "page_content", "") or "")).strip()
        if len(snippet) > 360:
            snippet = snippet[:357].rstrip() + "…"
        page = meta.get("page", "?")
        # Provenance: chunks ingested with a `book` tag (RxPrep); DiPiro
        # predates the tag, so default to it when absent.
        book = meta.get("book", "dipiro")
        info = BOOKS.get(book, BOOKS["dipiro"])
        cites.append(
            {
                "id": f"c{i + 1}",
                "marker": i + 1,
                "book": book,
                # Always prefer the curated label over raw file-path metadata.
                "source": info["source"],
                "section": meta.get("section") or info["section"],
                "page": f"p. {page}" if page != "?" else "—",
                "snippet": snippet or "(no text)",
                "relevance": round(float(rel), 2) if rel is not None else 0.0,
                "tier": tier_from_relevance(rel),
            }
        )
    return cites


def error_event(exc: AriaStageError) -> dict[str, Any]:
    """The one and only way a failure reaches the browser.

    Note what is absent: no confidence, no evidenceTier, no citations, and
    nothing that the UI could render as answer prose.
    """
    return {
        "type": "error",
        "stage": exc.stage,
        "code": exc.code or "provider_error",
        "message": exc.public_message(),
    }


def error_from_state(failure: AriaFailure) -> dict[str, Any]:
    """Build the error event from the failure the graph recorded."""
    return {
        "type": "error",
        "stage": failure["stage"],
        "code": failure["code"] or "provider_error",
        "message": failure["message"],
    }


SCOPE_NOTE = {
    "kind": "scope",
    "text": ("ARIA answers pharmacotherapy questions only, grounded in DiPiro's Pharmacotherapy."),
}
CAUTION_NOTE = {
    "kind": "caution",
    "text": (
        "Generated from textbook evidence — verify against current guidelines and patient context."
    ),
}


async def run_consultation(query: str) -> AsyncIterator[str]:
    """Drive the graph and translate its events into SSE.

    The only pipeline fact this function knows is which steps exist, so it
    can show them pending before the graph reaches them. Everything else —
    order, routing, what each step reports — comes from the graph.
    """
    steps = base_steps()
    by_id = {s["id"]: s for s in steps}

    def steps_event() -> str:
        return sse({"type": "steps", "steps": [dict(s) for s in steps]})

    final: dict[str, Any] | None = None

    async for event in stream_aria(query):
        kind = event["type"]

        if kind == "step":
            step = by_id.get(event["id"])
            if step is None:
                continue
            step.update({k: v for k, v in event.items() if k != "type" and k != "id"})
            yield steps_event()

        elif kind == "token":
            yield sse({"type": "token", "chunk": event["text"]})

        elif kind == "final":
            final = event["state"]

    if final is None:  # pragma: no cover - stream_aria always ends with final
        return

    failure = final["failure"]
    if failure is not None:
        # Anything the graph never reached is reported as such, rather than
        # left spinning in the trace.
        for step in steps:
            if step["status"] == "pending":
                step.update(status="skipped", detail="Not reached")
        yield steps_event()
        yield sse(error_from_state(failure))
        yield sse({"type": "done"})
        return

    if not final["is_medical"]:
        yield sse(
            {
                "type": "meta",
                "evidenceTier": "limited",
                "confidence": 0,
                "citations": [],
                "safety": [SCOPE_NOTE],
            }
        )
        yield sse({"type": "done"})
        return

    confidence = final["confidence"]
    yield sse(
        {
            "type": "meta",
            "evidenceTier": tier_from_confidence(confidence) if confidence is not None else None,
            "confidence": confidence,
            "citations": build_citations(final["chunks"]),
            "safety": [CAUTION_NOTE],
        }
    )
    yield sse({"type": "done"})


@app.get("/api/health")
async def health() -> JSONResponse:
    """Health across both hard dependencies: the models and the evidence base.

    The evidence base is re-probed on request rather than served from the
    boot-time result, so a cluster that dies (or is restored) while the
    process is up is reflected without a restart.

    "ok" here is a claim that a consultation would actually succeed. It is
    downgraded to "degraded" whenever either dependency is unusable, because
    a status page that reported "ok" through a total outage is why this
    outage went unnoticed.
    """
    global _store
    _store = await asyncio.to_thread(check_store)

    healthy = _preflight.ok and _store.ok
    return JSONResponse(
        {
            "status": "ok" if healthy else "degraded",
            "backend": "aria-langgraph",
            "models": _preflight.as_dict(),
            "evidenceBase": _store.as_dict(),
        },
        status_code=200 if healthy else 503,
    )


@app.post("/api/consult")
async def consult(req: ConsultRequest, request: Request) -> StreamingResponse:
    key = client_key(request)
    limited = over_rate_limit(key)
    if limited:
        logger.warning("rate limit hit by %s", key)

    async def gen() -> AsyncIterator[str]:
        if limited:
            # Reported on the error channel like any other dead end, so the
            # UI shows a fault rather than an empty, apparently-fine reply.
            yield sse(
                {
                    "type": "error",
                    "stage": "transport",
                    "code": "rate_limited",
                    "message": (
                        "ARIA could not produce an answer: too many requests from this "
                        "client. Wait a moment and try again. No clinical content was "
                        "generated."
                    ),
                }
            )
            yield sse({"type": "done"})
            return

        try:
            async with _consult_slots:
                async for ev in run_consultation(req.query.strip()):
                    yield ev
        except Exception as exc:  # last resort — still never a token
            # The old code streamed `str(exc)` as a `token`, so the browser
            # rendered a stack trace as ARIA's grounded reply. Failures leave
            # through the error channel or not at all.
            logger.exception("unhandled consultation error")
            yield sse(error_event(wrap_provider_error(exc, "consultation", "unknown")))
            yield sse({"type": "done"})

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# Serve the built web frontend (web/dist) when it exists, so a single
# process can host both the API and the UI in production. Registered after
# the /api routes, so those keep precedence.
_DIST = os.path.join(ROOT, "web", "dist")
if os.path.isdir(_DIST):
    app.mount("/", StaticFiles(directory=_DIST, html=True), name="web")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

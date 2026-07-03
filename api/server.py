"""
ARIA bridge server.
------------------------------------------------------------------
Runs the real LangGraph pipeline (guardrail -> navigator -> generator ->
judge) and streams it to the web frontend as Server-Sent Events whose shape
matches `web/src/lib/client.ts` (ConsultationEvent): steps -> meta -> token
-> done. The frontend talks to this through Vite's /api proxy; if this server
is down, the UI transparently falls back to its built-in mock.

Run from the project root:
    aria_env/bin/uvicorn api.server:app --port 8000
"""

import os
import sys
import json
import time
import asyncio
import re

# --- Make the existing (sys.path-based) modules importable -----------------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)  # retriever/vectorstore use paths relative to the project root
for sub in ("", "agents", "llm", "retrieval", "vectorstore", "ingestion", "graph"):
    p = os.path.join(ROOT, sub)
    if p not in sys.path:
        sys.path.insert(0, p)

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Real ARIA components (imported lazily inside handlers where heavy).
from guardrail_agent import check_guardrail  # noqa: E402

app = FastAPI(title="ARIA Bridge")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cache the reranking retriever (loads the embedding model + Qdrant once).
_retriever = None
_retriever_lock = asyncio.Lock()


async def get_retriever():
    global _retriever
    async with _retriever_lock:
        if _retriever is None:
            from reranker import get_balanced_retriever

            # Source-balanced: pull a global set + a guaranteed RxPrep set,
            # then Cohere-rerank to the best 5 across both books.
            _retriever = await asyncio.to_thread(get_balanced_retriever, 14, 8, 5)
    return _retriever


class ConsultRequest(BaseModel):
    query: str


def sse(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


def base_steps():
    return [
        {"id": "guardrail", "label": "Guardrail", "detail": "Confirming the query is in clinical scope", "status": "pending"},
        {"id": "navigator", "label": "Navigator", "detail": "Retrieving & reranking DiPiro passages", "status": "pending"},
        {"id": "generator", "label": "Generator", "detail": "Synthesizing a grounded answer", "status": "pending"},
        {"id": "judge", "label": "Judge", "detail": "Scoring faithfulness & evidence strength", "status": "pending"},
    ]


def tier_from_confidence(c: float) -> str:
    if c >= 0.8:
        return "strong"
    if c >= 0.6:
        return "moderate"
    return "limited"


def tier_from_relevance(r) -> str:
    try:
        r = float(r)
    except (TypeError, ValueError):
        return "moderate"
    if r >= 0.75:
        return "strong"
    if r >= 0.5:
        return "moderate"
    return "limited"


# How each source book is cited and labelled in the UI.
BOOKS = {
    "dipiro": {"source": "DiPiro's Pharmacotherapy", "section": "A Pathophysiologic Approach, 12e"},
    "rxprep": {"source": "RxPrep NAPLEX Course Book (2025)", "section": "UWorld · NAPLEX review"},
}


def build_citations(chunks):
    cites = []
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
                "id": f"c{i+1}",
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


async def stream_tokens(text: str):
    for tok in re.findall(r"\s+|\S+", text):
        yield sse({"type": "token", "chunk": tok})
        await asyncio.sleep(0.014 if not re.match(r"[.,;:]", tok) else 0.03)


async def run_consultation(query: str):
    steps = base_steps()

    def patch(step_id, **kw):
        for s in steps:
            if s["id"] == step_id:
                s.update(kw)

    def steps_event():
        return sse({"type": "steps", "steps": [dict(s) for s in steps]})

    # 1 — Guardrail
    patch("guardrail", status="active")
    yield steps_event()
    t0 = time.time()
    try:
        is_medical = await asyncio.to_thread(check_guardrail, query)
    except Exception as e:  # noqa: BLE001
        is_medical = True
        print("guardrail error:", e)
    patch(
        "guardrail",
        status="done",
        durationMs=int((time.time() - t0) * 1000),
        metric="medical · in scope" if is_medical else "out of scope",
        detail="Clinical pharmacotherapy query" if is_medical else "Query is outside clinical scope",
    )
    yield steps_event()

    if not is_medical:
        for sid in ("navigator", "generator", "judge"):
            patch(sid, status="skipped", detail="Skipped — out of scope")
        yield steps_event()
        yield sse(
            {
                "type": "meta",
                "evidenceTier": "limited",
                "confidence": 0,
                "citations": [],
                "safety": [
                    {
                        "kind": "scope",
                        "text": "ARIA answers pharmacotherapy questions only, grounded in DiPiro's Pharmacotherapy.",
                    }
                ],
            }
        )
        msg = (
            "That falls outside my scope. I'm **ARIA**, a clinical pharmacotherapy assistant — "
            "I can help with drug selection, dosing, monitoring, interactions, and the evidence "
            "behind therapeutic decisions, grounded in *DiPiro's Pharmacotherapy*."
        )
        async for ev in stream_tokens(msg):
            yield ev
        yield sse({"type": "done"})
        return

    # 2 — Navigator (retrieve + Cohere rerank)
    patch("navigator", status="active")
    yield steps_event()
    t0 = time.time()
    from navigator_agent import optimize_query

    retriever = await get_retriever()
    optimized = await asyncio.to_thread(optimize_query, query)
    chunks = await asyncio.to_thread(retriever.invoke, optimized)
    patch(
        "navigator",
        status="done",
        durationMs=int((time.time() - t0) * 1000),
        metric=f"retrieved → {len(chunks)} reranked",
        detail="Top passages selected by relevance",
    )
    yield steps_event()

    # 3 — Generator
    patch("generator", status="active")
    yield steps_event()
    t0 = time.time()
    from generator import generate_answer

    answer = await asyncio.to_thread(generate_answer, query, chunks)
    patch(
        "generator",
        status="done",
        durationMs=int((time.time() - t0) * 1000),
        metric=f"{len(chunks)} sources cited",
        detail="Answer grounded in retrieved passages",
    )
    yield steps_event()

    # 4 — Judge (compute before reveal so tier/confidence are real)
    patch("judge", status="active")
    yield steps_event()
    t0 = time.time()
    from judge_agent import judge_answer

    try:
        judgment = await asyncio.to_thread(judge_answer, query, answer, chunks)
        confidence = float(judgment.get("confidence", 0.5))
    except Exception as e:  # noqa: BLE001
        print("judge error:", e)
        confidence = 0.5
    confidence = max(0.0, min(1.0, confidence))

    yield sse(
        {
            "type": "meta",
            "evidenceTier": tier_from_confidence(confidence),
            "confidence": confidence,
            "citations": build_citations(chunks),
            "safety": [
                {
                    "kind": "caution",
                    "text": "Generated from textbook evidence — verify against current guidelines and patient context.",
                }
            ],
        }
    )

    async for ev in stream_tokens(answer):
        yield ev

    patch(
        "judge",
        status="done",
        durationMs=int((time.time() - t0) * 1000),
        metric=f"{round(confidence * 100)}% confidence",
        detail="Answer scored for faithfulness to cited sources",
    )
    yield steps_event()
    yield sse({"type": "done"})


@app.get("/api/health")
async def health():
    return JSONResponse({"status": "ok", "backend": "aria-langgraph"})


@app.post("/api/consult")
async def consult(req: ConsultRequest):
    async def gen():
        try:
            async for ev in run_consultation(req.query.strip()):
                yield ev
        except Exception as e:  # noqa: BLE001
            print("consult error:", e)
            yield sse({"type": "token", "chunk": f"\n\nThe consultation failed: {e}"})
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

# ARIA — Clinical Pharmacotherapy Assistant

ARIA is a multi-agent, retrieval-augmented clinical assistant that answers
pharmacotherapy questions with evidence grounded in two reference texts:
**DiPiro's Pharmacotherapy: A Pathophysiologic Approach (12e)** and the
**RxPrep NAPLEX Course Book (2025)**. Every answer is generated strictly from
retrieved textbook passages, scored for faithfulness before it is shown, and
delivered with page-level citations, an evidence tier, and a confidence score.

---

## How it works

A LangGraph state machine routes every query through four specialised agents:

```
                 ┌────────────┐
   query ──────► │ Guardrail  │── out of scope ──► polite refusal
                 └─────┬──────┘
                       │ in scope
                 ┌─────▼──────┐
                 │ Navigator  │  rewrites the query, retrieves from Qdrant,
                 └─────┬──────┘  reranks with a cross-encoder
                       │ top passages
                 ┌─────▼──────┐
                 │ Generator  │  synthesises an answer from the passages only
                 └─────┬──────┘
                       │ draft answer
                 ┌─────▼──────┐
                 │   Judge    │  scores groundedness + relevance (0–1)
                 └─────┬──────┘
                       │
        confidence ≥ 0.7 ──► final answer (with citations & confidence)
        confidence < 0.7 ──► regenerate (up to 3 attempts)
```

- **Guardrail** — classifies whether the query is within clinical scope;
  everything else is refused before any retrieval happens.
- **Navigator** — rewrites the user's question into an optimised medical
  search query, then performs **source-balanced retrieval**: a global
  candidate set plus a guaranteed RxPrep set (via a metadata filter), so the
  smaller book is never drowned out by the larger one. Cohere's
  `rerank-english-v3.0` cross-encoder then keeps only the genuinely most
  relevant passages.
- **Generator** — produces the answer from the retrieved passages only
  (Llama 3.3 70B via Groq), so responses stay traceable to the source texts.
- **Judge** — independently scores the draft for groundedness and relevance.
  Low-confidence answers are regenerated; the score is surfaced to the user
  as a confidence gauge and evidence tier.

## Retrieval stack

| Layer | Choice |
|---|---|
| Embeddings | `all-MiniLM-L6-v2` (384-dim, normalised) |
| Vector store | Qdrant Cloud — collection `aria_medical`, cosine distance |
| Corpus | 31,000+ chunks across both books, with source/book/page metadata |
| First-stage search | Dense similarity + MMR, source-balanced across books |
| Second-stage rerank | Cohere `rerank-english-v3.0` cross-encoder |

Embeddings are computed once during ingestion and served from Qdrant Cloud,
which keeps the deployed footprint small — the app itself only embeds the
incoming query at request time.

## Web experience

The frontend (React + TypeScript + Vite + Tailwind) presents each answer as a
**consultation ledger**: prose on the left, a live evidence margin on the
right. The agent pipeline streams its progress step by step over Server-Sent
Events, and every citation shows its source book, page, snippet, and
relevance tier. See [`web/README.md`](web/README.md) for details.

## Project structure

```
aria/
├── agents/              # Guardrail, Navigator and Judge agents
├── api/                 # FastAPI bridge server (SSE streaming)
├── graph/               # LangGraph pipeline: state, nodes, routing
├── ingestion/           # PDF loading, OCR, cleaning, chunking, embedding
├── llm/                 # LLM setup (Groq), prompts, answer generator
├── retrieval/           # Retriever + source-balanced Cohere reranking
├── vectorstore/         # Qdrant Cloud store loader
├── web/                 # React frontend (consultation ledger UI)
├── migrate_to_qdrant.py # One-time migration: local store → Qdrant Cloud
├── requirements.txt
└── .env.example
```

## Getting started

**Prerequisites:** Python 3.11+, Node 18+, and API keys for
[Groq](https://console.groq.com), [Cohere](https://dashboard.cohere.com) and
[Qdrant Cloud](https://cloud.qdrant.io).

```bash
# 1. Backend setup
python3 -m venv aria_env
source aria_env/bin/activate
pip install -r requirements.txt

# 2. Configure secrets
cp .env.example .env       # then fill in your keys

# 3. Run the API server
uvicorn api.server:app --port 8000

# 4. Run the frontend (separate terminal)
cd web
npm install
npm run dev                # http://localhost:5183
```

You can also exercise the pipeline directly from the command line:

```bash
python graph/aria_graph.py       # runs the full agent graph on test queries
python retrieval/retriever.py    # retrieval smoke test
```

> **Note on source texts:** the reference PDFs are copyrighted and are not
> included in this repository. The ingestion pipeline (`ingestion/`) documents
> how the corpus was built: PDF parsing (with OCR for scanned pages) →
> cleaning → chunking → embedding → upload to Qdrant.

## Safety posture

ARIA is an educational project. Answers are generated from textbook evidence
and each response carries an explicit caution to verify against current
guidelines and patient context. It is not a substitute for professional
medical judgement.

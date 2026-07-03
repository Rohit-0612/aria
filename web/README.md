# ARIA — The Consultation Ledger

A frontend for **ARIA**, an evidence-grounded clinical pharmacotherapy assistant
(multi-agent RAG over *DiPiro's Pharmacotherapy*). This is the **Consultation
Ledger** concept: a warm-archival, editorial interface where every answer reads
like a page from a clinical reference — prose on the left, a live **evidence
margin** on the right, and the agent reasoning made visible, not hidden.

## Run it

```bash
cd web
npm install
npm run dev      # http://localhost:5183
```

Other scripts: `npm run build` (type-check + production build), `npm run preview`.

Requires Node 18+. No environment variables or API keys — the UI ships with a
realistic mock transport so it runs fully standalone.

## What makes it different

- **The evidence margin.** Citations aren't `[1]` brackets — they're typographic
  superscripts that *dock into a side rail* as the answer streams, like footnotes
  settling into a textbook. Hover a marker → its DiPiro snippet peeks; the matching
  margin card highlights in sync.
- **The reasoning trace.** The real LangGraph pipeline (guardrail → navigator →
  generator → judge) is rendered as a vertical signal chain with a traveling
  filament and per-node instrument readouts ("248 chunks → 3 reranked", "91%
  confidence"). It collapses to one ledger line when done, but stays inspectable.
- **Evidence tier as a first-class object.** A calibrated 3-segment strength mark
  + roman-numeral stamp + a confidence arc gauge, revealed the moment the Judge
  returns.
- **A real point of view.** Bone-paper + warm ink, a single saffron accent, oxblood
  reserved only for caution. Fraunces (display) / Spectral (clinical prose) / IBM
  Plex Mono (instrument labels). Dark mode is a first-class theme, not an invert.
- **Command palette** (`⌘K`), keyboard-navigable, with seeded consults and
  free-form ask.

## Architecture

```
src/
  lib/
    types.ts       # API contract — mirrors graph/state.py (AriaState)
    client.ts      # transport boundary: consult() yields SSE-shaped events
    mockData.ts    # realistic DiPiro-grounded responses (warfarin, metformin, …)
    tiers.ts       # evidence-tier metadata
  hooks/
    useConsultation.ts   # owns the transcript, drives streaming
    useTheme.ts / useReducedMotion.ts
  components/        # Masthead, ReasoningTrace, EvidenceTierMark, SourcesRail,
                     # CitationMarker, Composer, CommandPalette, EmptyState, …
  styles/tokens.css  # design tokens (light + dark)
```

## Connecting the real backend

The entire app talks to one function — `consult(query)` in `src/lib/client.ts` —
which yields a typed `ConsultationEvent` stream (`steps` → `meta` → `token` →
`done`). To go live, replace its body with an SSE reader against the FastAPI/
LangGraph backend that emits the same event shape. `vite.config.ts` already
proxies `/api` to `http://127.0.0.1:8000`. Nothing else in the UI changes.

The wire types in `src/lib/types.ts` are the single source of truth and map
directly onto the backend's `AriaState` (`query`, `is_medical`, `chunks`,
`answer`, `confidence`), enriched with the structured fields a clinical UI needs:
`evidenceTier`, resolved `citations[]`, and a readable `agentSteps[]` trace.

## Accessibility & performance

- Semantic landmarks, keyboard-navigable palette and citations, visible focus
  rings, `role="meter"`/`role="tooltip"`/`aria-expanded` where appropriate.
- Honors `prefers-reduced-motion` (animations collapse; the pipeline resolves
  instantly).
- Transform/opacity-only animation, hairline borders over heavy shadows; the
  production bundle gzips to ~99 kB JS.

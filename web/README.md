# ARIA — The Consultation Ledger

A frontend for **ARIA**, an evidence-grounded clinical pharmacotherapy assistant
(multi-agent RAG over *DiPiro's Pharmacotherapy*). A warm-archival, editorial
take on a chat interface: the journal typography and the visible agent
reasoning of a clinical reference, in the rhythm of a conversation — questions
tucked to the right, ARIA answering in the open, and every claim one tap from
the passage it was retrieved from.

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

- **The cover page.** Opening the app shows an animated title page: the ARIA
  colophon draws itself in ink, the title rises off the baseline letter by
  letter, and the cover lifts away into the consultation page (click or press
  any key to skip; respects reduced-motion).
- **One consultation surface.** The transcript scrolls inside a single framed
  sheet with the composer docked at its foot, so the app reads as a room you're
  talking in — not a document that reprints its masthead for every question.
- **The thinking strip.** The real LangGraph pipeline (guardrail → navigator →
  generator → judge) opens above the answer as a live signal chain with a
  traveling filament and per-node readouts ("5 passages kept"), then
  folds itself into one receipt line — "Reasoned in 4.2s" — that reopens on
  click. Visible when it matters, silent when it doesn't.
- **Citations that go somewhere.** The generator cites passages inline as
  `[[n]]`; the reader sees typographic superscripts (several set as ¹,³),
  resolving while the answer is still streaming because the passages arrive
  before the prose. Hover peeks at the passage, clicking pins it open in the
  source rail beneath the reply.
- **Instruments, not furniture.** How well grounded the Judge found the
  answer, its score arc, and the source count sit in one quiet row under each
  answer, arriving a beat after the prose lands. The badge says *grounded*,
  not *certain*: it measures faithfulness to two textbooks, not the GRADE
  quality of the clinical evidence behind them, and is not labelled as if it
  did.
- **Follow-ups.** The last two exchanges travel with each question, so "and in
  pregnancy?" is understood. The receipt line shows how it was read
  ("Follow-up read as: …"), so a wrong guess is visible rather than silent.
- **A real point of view.** Bone-paper + warm ink, a single saffron accent, oxblood
  reserved only for caution. Fraunces (display) / Spectral (clinical prose) / IBM
  Plex Mono (instrument labels). Dark mode is a first-class theme, not an invert.
- **Command palette** (`⌘K`), keyboard-navigable, with seeded consults and
  free-form ask.
- **One build, phone to desktop.** Not a separate mobile site: the shell sizes
  itself from the *visual* viewport so an iOS keyboard lifts the composer
  instead of burying it, the reply gutter collapses so prose keeps the full
  line on a phone, citation markers skip the hover-peek on touch and open the
  passage directly, and safe-area insets keep content clear of the notch and
  home indicator.

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
  components/        # Masthead, MessageTurn, ThinkingStrip, AnswerMeta,
                     # SourceRail, CitationMarker, Composer, CommandPalette, …
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

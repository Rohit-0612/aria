# ARIA — The Consultation Ledger

A frontend for **ARIA**, an evidence-grounded clinical pharmacotherapy assistant
(multi-agent RAG over *DiPiro's Pharmacotherapy*). A broadsheet take on a chat
interface: newsprint, ink slabs and a condensed display serif, with the visible
agent reasoning of a clinical reference, in the rhythm of a conversation —
questions printed as ink slips on the right, ARIA answering in the open, and
every claim one tap from the passage it was retrieved from.

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

- **ARIA, dispensed.** Opening the app, the nameplate rises letter by letter
  on the ink ground; a capsule draws itself around it so the name becomes its
  label, fills in vermilion and newsprint, gives a small shake, and cracks open
  along its seam — the halves slide apart, granules spill out, and the front
  page is behind them (click or press any key to skip).
- **Page turns through a paper curtain.** One WebGL fragment shader
  (`lib/curtain.ts`, no library) draws a torn sheet of newsprint. It is torn
  across the page for a **new consult**, and swaps the **Day
  and Night editions** (light and dark) under a sheet of the other ink. Without
  WebGL, or under reduced motion, a flat sheet slides or fades instead.
- **A front page, not an empty state.** A dateline, the nameplate on an ink
  slab whose letters rise as the curtain tears, a standfirst, figures from the
  evaluation that count up (27,104 passages · 2 texts · 4 agents · 0.90
  groundedness), an interactive halftone plate whose dots swell around the
  pointer, and "In this issue": four consults set as headlines that a
  hand-drawn loop inks around on hover.
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
- **The Judge's verdict, stamped.** Once the prose lands, a perforated postage
  stamp thumps down under the answer, inked in its tier colour, the score
  counting up in the middle. It says *grounded*, not *certain*: it measures
  faithfulness to two textbooks, not the GRADE quality of the clinical
  evidence behind them, and is not labelled as if it did. When the Judge
  could not score the answer the stamp reads **Not adjudicated** in oxblood
  and carries no number.
- **Follow-ups.** The last two exchanges travel with each question, so "and in
  pregnancy?" is understood. The receipt line shows how it was read
  ("Follow-up read as: …"), so a wrong guess is visible rather than silent.
- **A real point of view.** Newsprint and printer's ink with a paper grain over
  everything, one vermilion spot colour, oxblood reserved only for caution.
  Melodrama (display, self-hosted, ITF Free Font License) / Spectral (clinical
  prose) / IBM Plex Mono (instrument labels). The Night edition prints the
  sheet in ink — a first-class theme, not an invert.
- **Small motion, everywhere it helps.** Labels roll over on hover, the send
  button leans toward the pointer, and on desktop an ink badge beside the
  cursor names what a click will do ("Ask ↗").
- **Command palette** (`⌘K`), keyboard-navigable, with seeded consults and
  free-form ask, set as the paper's index on an ink sheet that wipes down.
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
    curtain.ts     # the torn-paper WebGL curtain (page turns)
  components/        # CapsuleCover, Curtain, Masthead, EmptyState, MessageTurn,
                     # ThinkingStrip, AnswerMeta, VerdictStamp, SourceRail,
                     # CitationMarker, Composer, CommandPalette, Halftone,
                     # Cursor, fx (Roll, Doodle, RiseChars, CountUp), …
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
  rings; the verdict stamp and halftone plate are labelled images, with
  `role="tooltip"`/`aria-expanded` where appropriate. The cursor badge and
  magnetic pull are desktop-only and purely decorative.
- Honors `prefers-reduced-motion` (the capsule appears finished and fades, the curtain fades
  instead of tearing, letters and figures appear set, the pipeline resolves
  instantly).
- Transform/opacity-only animation, hairline borders over heavy shadows; the
  production bundle gzips to ~108 kB JS, plus 47 kB of self-hosted display font.

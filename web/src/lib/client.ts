import type {
  AgentStep,
  Citation,
  ConsultationError,
  EvidenceTier,
  SafetyNote,
} from './types';
import { recipeFor, OUT_OF_SCOPE } from './mockData';

/*
  Transport boundary.
  ------------------------------------------------------------------
  `consult()` yields a stream of events from ARIA's LangGraph backend over
  SSE: agent-step updates, then answer metadata, then streamed tokens, then
  done.

  On the mock, and why it is now opt-in only.
  ------------------------------------------------------------------
  `mockConsult` replays fixed, human-written sample answers so the UI can be
  developed without a backend. It previously ran as an automatic *fallback*:
  if a 2.5s probe of /api/health did not come back, `consult()` quietly
  served the mock instead.

  In production that is the worst failure this codebase can have. The mock's
  recipes are invented clinical content — doses, INR targets, eGFR
  thresholds — carried on the same `token` channel as a real answer, with
  page-level citations, an evidence tier and a confidence gauge attached.
  A reader had no way to tell them from adjudicated output. And the trigger
  was routine: a sleeping Hugging Face Space takes far longer than 2.5s to
  wake, so the ordinary cold start was enough to fire it.

  So the mock is now explicit and dev-only (VITE_ARIA_MOCK=1, which is never
  set in the production build). When the backend cannot be reached, the UI
  reports a transport failure — the same honest dead end the rest of the
  pipeline produces. No answer is always better than a fabricated one.
*/

/** Dev-only. Never set in the deployed build. */
const USE_MOCK =
  import.meta.env.DEV && import.meta.env.VITE_ARIA_MOCK === '1';

export type ConsultationEvent =
  | { type: 'steps'; steps: AgentStep[] }
  | {
      type: 'meta';
      /** Null when the Judge could not grade the answer. */
      evidenceTier: EvidenceTier | null;
      /** Null when not adjudicated. Never a placeholder number. */
      confidence: number | null;
      citations: Citation[];
      safety?: SafetyNote[];
    }
  /**
   * Answer prose only. The backend must never send a failure on this
   * channel — tokens are rendered as ARIA's reply and decorated with an
   * evidence tier, so an error arriving as a token would be presented to a
   * clinician with the authority of a cited answer.
   */
  | { type: 'token'; chunk: string }
  /** A failure. Terminal, and carries no confidence and no citations. */
  | ({ type: 'error' } & ConsultationError)
  | { type: 'done' };

const wait = (ms: number, signal?: AbortSignal) =>
  new Promise<void>((resolve, reject) => {
    if (signal?.aborted) return reject(new DOMException('aborted', 'AbortError'));
    const t = setTimeout(resolve, ms);
    signal?.addEventListener(
      'abort',
      () => {
        clearTimeout(t);
        reject(new DOMException('aborted', 'AbortError'));
      },
      { once: true },
    );
  });

function baseSteps(): AgentStep[] {
  return [
    {
      id: 'guardrail',
      label: 'Guardrail',
      detail: 'Confirming the query is in clinical scope',
      status: 'pending',
    },
    {
      id: 'navigator',
      label: 'Navigator',
      detail: 'Retrieving & reranking DiPiro passages',
      status: 'pending',
    },
    {
      id: 'generator',
      label: 'Generator',
      detail: 'Synthesizing a grounded answer',
      status: 'pending',
    },
    {
      id: 'judge',
      label: 'Judge',
      detail: 'Scoring faithfulness & evidence strength',
      status: 'pending',
    },
  ];
}

/** Tunable so reduced-motion / tests can run the pipeline instantly. */
export interface ConsultOptions {
  speed?: number; // multiplier; 1 = normal, 0 = instant
  signal?: AbortSignal;
}

async function* mockConsult(
  query: string,
  opts: ConsultOptions = {},
): AsyncGenerator<ConsultationEvent> {
  const k = opts.speed ?? 1;
  const signal = opts.signal;
  const steps = baseSteps();
  const recipe = recipeFor(query);
  const outOfScope = recipe === OUT_OF_SCOPE;

  const emit = (): ConsultationEvent => ({ type: 'steps', steps: steps.map((s) => ({ ...s })) });
  const set = (id: AgentStep['id'], patch: Partial<AgentStep>) => {
    const s = steps.find((x) => x.id === id)!;
    Object.assign(s, patch);
  };

  // 1 — Guardrail
  set('guardrail', { status: 'active' });
  yield emit();
  await wait(560 * k, signal);
  set('guardrail', {
    status: 'done',
    durationMs: 540,
    metric: outOfScope ? 'out of scope' : 'medical · in scope',
    detail: outOfScope ? 'Query is outside clinical scope' : 'Clinical pharmacotherapy query',
  });
  yield emit();

  if (outOfScope) {
    for (const id of ['navigator', 'generator', 'judge'] as const) {
      set(id, { status: 'skipped', detail: 'Skipped — out of scope' });
    }
    yield emit();
    yield {
      type: 'meta',
      evidenceTier: OUT_OF_SCOPE.evidenceTier,
      confidence: OUT_OF_SCOPE.confidence,
      citations: OUT_OF_SCOPE.citations,
      safety: OUT_OF_SCOPE.safety,
    };
    yield* streamTokens(OUT_OF_SCOPE.content, k, signal);
    yield { type: 'done' };
    return;
  }

  // 2 — Navigator (retrieve + Cohere rerank)
  set('navigator', { status: 'active' });
  yield emit();
  await wait(1180 * k, signal);
  set('navigator', {
    status: 'done',
    durationMs: 1160,
    metric: `248 chunks → ${recipe.citations.length} reranked`,
    detail: 'Top passages selected by relevance',
  });
  yield emit();

  // 3 — Generator (then streams)
  set('generator', { status: 'active' });
  yield emit();
  await wait(900 * k, signal);
  set('generator', {
    status: 'done',
    durationMs: 880,
    metric: `${recipe.citations.length} sources cited`,
    detail: 'Answer grounded in retrieved passages',
  });
  yield emit();

  // Reveal answer metadata (tier + citations dock into the margin).
  yield {
    type: 'meta',
    evidenceTier: recipe.evidenceTier,
    confidence: recipe.confidence,
    citations: recipe.citations,
    safety: recipe.safety,
  };

  // Stream the prose.
  yield* streamTokens(recipe.content, k, signal);

  // 4 — Judge (confidence already known; reveal as a closing beat)
  set('judge', { status: 'active' });
  yield emit();
  await wait(720 * k, signal);
  set('judge', {
    status: 'done',
    durationMs: 700,
    metric:
      recipe.confidence !== null
        ? `${Math.round(recipe.confidence * 100)}% confidence`
        : 'not adjudicated',
    detail: 'Answer is faithful to cited sources',
  });
  yield emit();

  yield { type: 'done' };
}

/* ----------------------------------------------------------------------
   Live transport — talks to the FastAPI bridge (api/server.py) over SSE.
   The event shape is identical to the mock, so the UI is agnostic.
   ---------------------------------------------------------------------- */

async function* apiConsult(
  query: string,
  opts: ConsultOptions,
): AsyncGenerator<ConsultationEvent> {
  const res = await fetch('/api/consult', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
    signal: opts.signal,
  });
  if (!res.ok || !res.body) throw new Error(`ARIA backend responded ${res.status}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = '';
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const parts = buf.split('\n\n');
    buf = parts.pop() ?? '';
    for (const part of parts) {
      const line = part.split('\n').find((l) => l.startsWith('data:'));
      if (!line) continue;
      const json = line.slice(5).trim();
      if (json) yield JSON.parse(json) as ConsultationEvent;
    }
  }
}

/**
 * Public transport. Always the live ARIA backend, unless the dev-only mock
 * is explicitly enabled. A backend failure surfaces as a failure: there is
 * no silent fallback to sample content.
 */
export async function* consult(
  query: string,
  opts: ConsultOptions = {},
): AsyncGenerator<ConsultationEvent> {
  if (USE_MOCK) {
    yield* mockConsult(query, opts);
    return;
  }
  // Errors propagate to useConsultation, which renders them as a failed turn
  // with no prose, no citations and no certainty badge.
  yield* apiConsult(query, opts);
}

async function* streamTokens(
  content: string,
  k: number,
  signal?: AbortSignal,
): AsyncGenerator<ConsultationEvent> {
  // Split on whitespace but keep the separators so markdown survives.
  const tokens = content.match(/\s+|\S+/g) ?? [content];
  for (const tok of tokens) {
    yield { type: 'token', chunk: tok };
    // Slightly varied cadence reads as "alive" rather than mechanical.
    const base = /[.,;:]/.test(tok) ? 38 : 17;
    await wait((base + Math.random() * 22) * k, signal);
  }
}

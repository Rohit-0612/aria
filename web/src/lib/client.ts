import type { AgentStep, Citation, EvidenceTier, SafetyNote } from './types';
import { recipeFor, OUT_OF_SCOPE } from './mockData';

/*
  Transport boundary.
  ------------------------------------------------------------------
  `consult()` yields a stream of events that mirror what ARIA's LangGraph
  backend would emit over SSE: agent-step updates, then answer metadata,
  then streamed tokens, then done. Swapping the mock for a live backend
  means replacing the body of `consult` with an SSE reader that yields the
  same `ConsultationEvent` shape — nothing else in the app changes.
*/

export type ConsultationEvent =
  | { type: 'steps'; steps: AgentStep[] }
  | {
      type: 'meta';
      evidenceTier: EvidenceTier;
      confidence: number;
      citations: Citation[];
      safety?: SafetyNote[];
    }
  | { type: 'token'; chunk: string }
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
    metric: `${Math.round(recipe.confidence * 100)}% confidence`,
    detail: 'Answer is faithful to cited sources',
  });
  yield emit();

  yield { type: 'done' };
}

/* ----------------------------------------------------------------------
   Live transport — talks to the FastAPI bridge (api/server.py) over SSE.
   The event shape is identical to the mock, so the UI is agnostic.
   ---------------------------------------------------------------------- */

let liveProbe: Promise<boolean> | null = null;

function probeLive(): Promise<boolean> {
  if (!liveProbe) {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), 2500);
    const p = fetch('/api/health', { signal: ctrl.signal })
      .then((r) => r.ok)
      .catch(() => false)
      .finally(() => clearTimeout(t));
    liveProbe = p;
    // Cache "live", but never cache a negative result — so a transient blip
    // can't lock the whole session onto the offline mock.
    p.then((ok) => {
      if (!ok) liveProbe = null;
    });
  }
  return liveProbe;
}

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
 * Public transport. Uses the live ARIA backend when reachable, otherwise
 * transparently falls back to the in-browser mock — so the UI runs either way.
 */
export async function* consult(
  query: string,
  opts: ConsultOptions = {},
): AsyncGenerator<ConsultationEvent> {
  if (await probeLive()) {
    let started = false;
    try {
      for await (const ev of apiConsult(query, opts)) {
        started = true;
        yield ev;
      }
      return;
    } catch (err) {
      if ((err as DOMException)?.name === 'AbortError') throw err;
      // If the stream had already begun, surface the failure; only fall back
      // to the mock when the live backend never connected.
      if (started) throw err;
      liveProbe = null; // re-probe next time
    }
  }
  yield* mockConsult(query, opts);
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

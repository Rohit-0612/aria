/*
  ARIA wire types.
  ------------------------------------------------------------------
  These mirror the LangGraph backend (graph/state.py: AriaState) and the
  agent nodes (guardrail → navigator → generator → judge). The frontend
  enriches that minimal state with the structured fields a clinical UI
  needs: evidence tier, resolved citations, and a readable agent trace.

  Keep this file as the single source of truth for the API boundary so
  the mock transport (lib/mockClient) and a future FastAPI transport are
  drop-in interchangeable.
*/

/** Evidence strength, after the Judge weighs source quality. */
export type EvidenceTier = 'strong' | 'moderate' | 'limited';

/** The four real nodes of the ARIA graph. */
export type AgentId = 'guardrail' | 'navigator' | 'generator' | 'judge';

export type AgentStatus = 'pending' | 'active' | 'done' | 'skipped' | 'failed';

export interface AgentStep {
  id: AgentId;
  /** Human label, e.g. "Navigator". */
  label: string;
  /** One-line description of what this node is doing right now. */
  detail: string;
  status: AgentStatus;
  /** Wall-clock duration once complete, ms. */
  durationMs?: number;
  /** Optional instrument readout, e.g. "248 chunks → 6 reranked". */
  metric?: string;
}

/** A resolved DiPiro citation. `marker` is the in-text superscript number. */
export interface Citation {
  id: string;
  marker: number;
  /** Which source corpus the passage came from. */
  book?: 'dipiro' | 'rxprep' | string;
  /** e.g. "DiPiro's Pharmacotherapy, 12e". */
  source: string;
  /** e.g. "Ch. 8 · Venous Thromboembolism". */
  section: string;
  page: string;
  /** The retrieved passage this claim is grounded in. */
  snippet: string;
  /** Cohere rerank relevance, 0..1. */
  relevance: number;
  tier: EvidenceTier;
}

/**
 * A provider/LLM failure. Its presence is what tells the UI that this turn
 * produced NO clinical content — so no evidence tier, no confidence gauge,
 * no citations and no "grounded reply" byline may be rendered for it.
 */
export interface ConsultationError {
  /** Which pipeline stage failed, e.g. "generator". */
  stage: string;
  /** Provider error code, e.g. "model_not_found". */
  code: string;
  /** Reader-facing sentence. Never answer-shaped. */
  message: string;
}

/** Soft scope/safety note. Present but never alarmist. */
export interface SafetyNote {
  kind: 'scope' | 'caution' | 'interaction';
  text: string;
}

export interface UserMessage {
  id: string;
  role: 'user';
  content: string;
  createdAt: number;
}

export interface AssistantMessage {
  id: string;
  role: 'assistant';
  /**
   * Markdown-lite prose. Citation markers are encoded inline as
   * `[[n]]` and resolved against `citations` by marker number.
   */
  content: string;
  /**
   * Null until the Judge has actually graded the answer. It must never be
   * seeded with a placeholder tier: a non-null value here is rendered as a
   * GRADE certainty badge, so a default of 'moderate' put a
   * "MODERATE CERTAINTY" stamp on ungraded text — including error text.
   */
  evidenceTier: EvidenceTier | null;
  /** Judge confidence, 0..1. Null means "not adjudicated" — never 0.5. */
  confidence: number | null;
  citations: Citation[];
  agentSteps: AgentStep[];
  safety?: SafetyNote[];
  createdAt: number;
  /** Streaming lifecycle for the UI. `failed` is terminal and answer-free. */
  phase: 'reasoning' | 'streaming' | 'complete' | 'failed';
  /** Set only when the turn failed. Mutually exclusive with real content. */
  error?: ConsultationError;
}

export type Message = UserMessage | AssistantMessage;

/** Saved suggested consultations for the empty / first-run state. */
export interface PromptSeed {
  id: string;
  title: string;
  query: string;
  topic: string;
}

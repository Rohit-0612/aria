import type { EvidenceTier } from './types';

/*
  One three-step scale, read two ways.

  On an answer, the tier comes from the Judge's score: how fully the cited
  passages support what the answer says. On a passage, it comes from the
  reranker: how relevant that passage is to the question. Neither is a
  GRADE certainty rating, and neither is labelled as one. GRADE rates the
  quality of a body of clinical evidence from its study designs; ARIA has
  no access to study designs, only to whether its own answer is faithful to
  two textbooks. The badge used to read "High certainty · GRADE · RCT /
  meta-analysis", which claimed something nothing in the pipeline measures.
*/

interface TierMeta {
  tier: EvidenceTier;
  /** On an answer: how well the Judge found it grounded. */
  label: string;
  /** On a passage: how relevant the reranker found it. */
  relevanceLabel: string;
  /** Tooltip under the answer badge — what the label actually measures. */
  gloss: string;
  /** Filled segments out of 3 on the strength mark. */
  segments: number;
  /** Tailwind text color token. */
  color: string;
  /** Tailwind background tint token (with opacity applied at use site). */
  tint: string;
}

export const TIERS: Record<EvidenceTier, TierMeta> = {
  strong: {
    tier: 'strong',
    label: 'Well grounded',
    relevanceLabel: 'High relevance',
    gloss: 'Judge ≥ 0.80 · claims are supported by the cited passages',
    segments: 3,
    color: 'text-tier-strong',
    tint: 'bg-tier-strong',
  },
  moderate: {
    tier: 'moderate',
    label: 'Partly grounded',
    relevanceLabel: 'Moderate relevance',
    gloss: 'Judge 0.60–0.79 · some claims are thinly supported',
    segments: 2,
    color: 'text-tier-moderate',
    tint: 'bg-tier-moderate',
  },
  limited: {
    tier: 'limited',
    label: 'Weakly grounded',
    relevanceLabel: 'Low relevance',
    gloss: 'Judge below 0.60 · check each claim against its source',
    segments: 1,
    color: 'text-tier-limited',
    tint: 'bg-tier-limited',
  },
};

export function tierOf(t: EvidenceTier): TierMeta {
  return TIERS[t];
}

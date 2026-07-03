import type { EvidenceTier } from './types';

interface TierMeta {
  tier: EvidenceTier;
  label: string;
  /** Roman numeral stamp shown in the margin. */
  numeral: string;
  /** Short clinical gloss. */
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
    label: 'High certainty',
    numeral: 'I',
    gloss: 'GRADE · RCT / meta-analysis',
    segments: 3,
    color: 'text-tier-strong',
    tint: 'bg-tier-strong',
  },
  moderate: {
    tier: 'moderate',
    label: 'Moderate certainty',
    numeral: 'II',
    gloss: 'GRADE · cohort / guideline',
    segments: 2,
    color: 'text-tier-moderate',
    tint: 'bg-tier-moderate',
  },
  limited: {
    tier: 'limited',
    label: 'Low certainty',
    numeral: 'III',
    gloss: 'GRADE · expert opinion',
    segments: 1,
    color: 'text-tier-limited',
    tint: 'bg-tier-limited',
  },
};

export function tierOf(t: EvidenceTier): TierMeta {
  return TIERS[t];
}

import { motion } from 'framer-motion';
import type { EvidenceTier } from '../lib/types';
import { tierOf } from '../lib/tiers';
import { CountUp } from './fx';
import { useReducedMotion } from '../hooks/useReducedMotion';
import { cn } from '../lib/utils';

/*
  The Judge's verdict, stamped on the reply.

  A perforated postage stamp inked in the tier's colour — the score in the
  middle, the verdict along the foot — that lands with a thump once the
  answer has finished printing. When the Judge could not score the answer it
  says so in oxblood and carries no number: an empty stamp is never a score.
*/

interface Props {
  tier: EvidenceTier | null;
  /** Judge score 0–1; null when the Judge never adjudicated. */
  confidence: number | null;
}

const INK: Record<EvidenceTier, string> = {
  strong: 'text-tier-strong',
  moderate: 'text-tier-moderate',
  limited: 'text-tier-limited',
};

const SHORT: Record<EvidenceTier, string> = {
  strong: 'Well grounded',
  moderate: 'Partly grounded',
  limited: 'Weakly grounded',
};

export function VerdictStamp({ tier, confidence }: Props) {
  const reduced = useReducedMotion();
  const adjudicated = confidence !== null;
  const meta = tier ? tierOf(tier) : null;
  const ink = !adjudicated ? 'text-oxblood' : tier ? INK[tier] : 'text-ink-soft';
  const scored = adjudicated && confidence > 0;

  return (
    <motion.span
      initial={reduced ? false : { scale: 1.9, rotate: -14, opacity: 0 }}
      animate={{ scale: 1, rotate: -4, opacity: 1 }}
      transition={
        reduced ? { duration: 0 } : { type: 'spring', stiffness: 420, damping: 17, mass: 0.9, delay: 0.15 }
      }
      className="stamp block h-[76px] w-[92px] shrink-0"
      role="img"
      aria-label={
        adjudicated
          ? `Judge verdict: ${meta?.label ?? 'graded'}${scored ? `, score ${confidence.toFixed(2)}` : ''}`
          : 'Not adjudicated: the Judge was unavailable'
      }
    >
      <span
        className={cn(
          'stamp-in flex flex-col items-center justify-between px-1 py-[5px] text-center',
          ink,
        )}
      >
        <span className="font-mono text-[0.5rem] uppercase leading-none tracking-[0.16em]">
          Judge
        </span>
        <b className="head text-[1.75rem] leading-[0.8]">
          {scored ? <CountUp value={confidence} decimals={2} ms={1100} reduced={reduced} /> : '—'}
        </b>
        <span className="whitespace-nowrap font-mono text-[0.44rem] uppercase leading-none tracking-[0.08em]">
          {adjudicated ? (tier ? SHORT[tier] : 'Graded') : 'Not adjudicated'}
        </span>
      </span>
    </motion.span>
  );
}

import { motion } from 'framer-motion';
import type { EvidenceTier } from '../lib/types';
import { tierOf } from '../lib/tiers';
import { ConfidenceGauge } from './ConfidenceGauge';
import { cn } from '../lib/utils';

/*
  Margin classification box — the article's GRADE level of evidence and the
  Judge's peer-review confidence, set as a boxed marginal note (Tufte-style).
*/

export function EvidenceLevel({
  tier,
  confidence,
  animate = true,
}: {
  tier: EvidenceTier;
  confidence: number;
  animate?: boolean;
}) {
  const meta = tierOf(tier);

  return (
    <motion.div
      initial={animate ? { opacity: 0, y: 8 } : false}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      className="border border-rule/30 bg-surface/60"
    >
      <div className="border-b border-line px-3 py-1.5">
        <span className="sec !text-[0.54rem]">Level of Evidence</span>
      </div>

      <div className="flex items-start gap-3 px-3 py-3">
        <span
          className={cn(
            'grid h-9 w-9 shrink-0 place-items-center border font-display text-xl leading-none',
            meta.color,
          )}
          style={{ borderColor: 'currentColor' }}
        >
          {meta.numeral}
        </span>
        <div className="min-w-0">
          <span className={cn('block font-prose text-[0.92rem] font-medium leading-tight', meta.color)}>
            {meta.label}
          </span>
          <span className="mt-0.5 block font-mono text-[0.56rem] uppercase tracking-[0.08em] text-ink-faint">
            {meta.gloss}
          </span>
          <div className="mt-2 flex items-end gap-[3px]" aria-hidden>
            {[0, 1, 2].map((i) => (
              <motion.span
                key={i}
                initial={animate ? { scaleY: 0.2, opacity: 0 } : false}
                animate={{ scaleY: 1, opacity: 1 }}
                transition={{ delay: 0.08 * i, duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
                style={{ originY: 1 }}
                className={cn(
                  'w-2 rounded-[1px]',
                  i < meta.segments ? meta.tint : 'bg-line-strong/50',
                  i === 0 && 'h-2.5',
                  i === 1 && 'h-4',
                  i === 2 && 'h-5',
                )}
              />
            ))}
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3 border-t border-line px-3 py-3">
        <ConfidenceGauge value={confidence} size={42} animate={animate} />
        <div>
          <span className="block font-prose text-[0.82rem] font-medium leading-tight text-ink">
            Peer-review score
          </span>
          <span className="mt-0.5 block font-mono text-[0.55rem] uppercase tracking-[0.1em] text-ink-faint">
            Adjudicated · Judge Agent
          </span>
        </div>
      </div>
    </motion.div>
  );
}

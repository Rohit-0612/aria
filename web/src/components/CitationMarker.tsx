import { useId, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { useCitations } from './citationContext';
import { shortSource } from './SourceRail';
import { useIsTouch } from '../hooks/useViewport';
import { tierOf } from '../lib/tiers';
import { cn } from '../lib/utils';

/*
  Inline citation marker — a small superscript numeral, not an ugly bracket.
  Hovering peeks at the grounded passage; clicking opens that passage in the
  source rail beneath the answer. On touch there is no hover to peek with, so
  a tap goes straight to the rail instead of flashing a popover first.
*/

export function CitationMarker({ marker }: { marker: number }) {
  const { byMarker, active, setActive, reveal } = useCitations();
  const [peek, setPeek] = useState(false);
  const touch = useIsTouch();
  const id = useId();
  const cite = byMarker.get(marker);
  if (!cite) return null;

  const meta = tierOf(cite.tier);
  const isActive = active === marker;

  const open = () => {
    setActive(marker);
    if (!touch) setPeek(true);
  };
  const close = () => {
    setActive(null);
    setPeek(false);
  };

  return (
    <span className="relative inline-block">
      <button
        type="button"
        aria-describedby={peek ? id : undefined}
        aria-label={`Source ${marker}: ${cite.section}, ${meta.label}`}
        onMouseEnter={open}
        onMouseLeave={close}
        onFocus={open}
        onBlur={close}
        onClick={(e) => {
          e.preventDefault();
          reveal(marker);
          setPeek(false);
        }}
        className={cn(
          /* A wider hit area on touch without disturbing the typography. */
          'mx-[0.5px] inline-flex align-super font-mono text-[0.66em] font-medium leading-none tabular-nums transition-colors',
          'px-[3px] py-[2px] -my-[2px] -mx-[2px]',
          isActive ? 'text-accent underline' : 'text-accent/90 hover:underline',
        )}
      >
        {marker}
      </button>

      <AnimatePresence>
        {peek && (
          <motion.span
            id={id}
            role="tooltip"
            initial={{ opacity: 0, y: 6, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 4, scale: 0.98 }}
            transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
            className="absolute bottom-[calc(100%+8px)] left-1/2 z-30 block w-[min(264px,calc(100vw-3rem))] -translate-x-1/2 rounded-[10px] border border-line-strong bg-surface-raised p-3 text-left shadow-peek"
          >
            <span className="flex items-center justify-between gap-2">
              <span className="label">{shortSource(cite)}</span>
              <span className={cn('font-mono text-[0.56rem] uppercase', meta.color)}>
                Tier {meta.numeral}
              </span>
            </span>
            <span className="mt-1 block font-mono text-[0.6rem] text-ink-soft">
              {cite.section} · {cite.page}
            </span>
            <span className="mt-2 block border-l-2 border-accent/40 pl-2.5 font-prose text-[0.8rem] italic leading-snug text-ink-soft">
              {cite.snippet}
            </span>
            <span className="mt-2.5 flex items-center gap-1.5">
              <span className="label !text-[0.52rem]">Rerank</span>
              <span className="h-1 flex-1 overflow-hidden rounded-full bg-line">
                <span
                  className="block h-full bg-accent/70"
                  style={{ width: `${Math.round(cite.relevance * 100)}%` }}
                />
              </span>
              <span className="font-mono text-[0.56rem] text-ink-faint">
                {cite.relevance.toFixed(2)}
              </span>
            </span>
            <span className="mt-2 block text-center font-mono text-[0.52rem] uppercase tracking-[0.12em] text-ink-faint/70">
              click to pin below
            </span>
          </motion.span>
        )}
      </AnimatePresence>
    </span>
  );
}

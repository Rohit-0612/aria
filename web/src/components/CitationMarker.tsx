import { Fragment, useId, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { motion } from 'framer-motion';
import { useCitations } from './citationContext';
import { shortSource } from './SourceRail';
import { useIsTouch } from '../hooks/useViewport';
import { tierOf } from '../lib/tiers';
import { cn } from '../lib/utils';

/*
  Inline citation marker — a small superscript numeral, not an ugly bracket.
  Hovering peeks at the grounded passage; clicking opens that passage in the
  source rail beneath the answer. The peek is portalled to <body> with fixed
  coordinates: markers also sit inside table cells, whose scrolling wrapper
  clipped an absolutely positioned popover to a sliver. On touch there is no hover to peek with, so
  a tap goes straight to the rail instead of flashing a popover first.
*/

/**
 * A run of markers, e.g. `[[1]][[3]]`, set as ¹,³. Markers that point at no
 * retrieved passage are dropped rather than drawn as dead superscripts — the
 * generator is told to cite only numbers it was given, and this is the
 * second lock on that door.
 */
export function CitationGroup({ markers }: { markers: number[] }) {
  const { byMarker } = useCitations();
  const known = [...new Set(markers)].filter((n) => byMarker.has(n));
  if (!known.length) return null;
  return (
    <>
      {known.map((n, i) => (
        <Fragment key={n}>
          {i > 0 && (
            <span aria-hidden className="align-super font-mono text-[0.66em] text-accent/60">
              ,
            </span>
          )}
          <CitationMarker marker={n} />
        </Fragment>
      ))}
    </>
  );
}

/** Matches the peek's `w-[min(264px,…)]`, for keeping it on screen. */
const PEEK_WIDTH = 264;

export function CitationMarker({ marker }: { marker: number }) {
  const { byMarker, active, setActive, reveal } = useCitations();
  const [peek, setPeek] = useState<{ x: number; y: number } | null>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const touch = useIsTouch();
  const id = useId();
  const cite = byMarker.get(marker);
  if (!cite) return null;

  const meta = tierOf(cite.tier);
  const isActive = active === marker;

  const open = () => {
    setActive(marker);
    const rect = buttonRef.current?.getBoundingClientRect();
    if (touch || !rect) return;
    // Centred over the numeral, kept inside the viewport on both sides.
    const half = Math.min(PEEK_WIDTH, window.innerWidth - 48) / 2;
    const x = Math.min(Math.max(rect.left + rect.width / 2, half + 8), window.innerWidth - half - 8);
    setPeek({ x, y: rect.top });
  };
  const close = () => {
    setActive(null);
    setPeek(null);
  };

  return (
    <span className="relative inline-block">
      <button
        ref={buttonRef}
        type="button"
        aria-describedby={peek ? id : undefined}
        aria-label={`Source ${marker}: ${shortSource(cite)}, ${cite.page}`}
        onMouseEnter={open}
        onMouseLeave={close}
        onFocus={open}
        onBlur={close}
        onClick={(e) => {
          e.preventDefault();
          reveal(marker);
          setPeek(null);
        }}
        className={cn(
          /* A taller hit area for touch without disturbing the line; the
             horizontal padding is cancelled by an equal negative margin so the
             numeral sits against its word like a printed superscript. */
          'inline-flex align-super font-mono text-[0.66em] font-medium leading-none tabular-nums transition-colors',
          'px-[2px] py-[2px] -my-[2px] -mx-[2px]',
          isActive ? 'text-accent underline' : 'text-accent/90 hover:underline',
        )}
      >
        {marker}
      </button>

      {peek &&
        createPortal(
          <motion.span
            id={id}
            role="tooltip"
            // Anchored at the numeral's top-centre and lifted by its own
            // height; framer owns `transform`, so the offset is set here.
            style={{ left: peek.x, top: peek.y - 8 }}
            initial={{ opacity: 0, scale: 0.97, x: '-50%', y: '-96%' }}
            animate={{ opacity: 1, scale: 1, x: '-50%', y: '-100%' }}
            transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
            className="pointer-events-none fixed z-50 block w-[min(264px,calc(100vw-3rem))] rounded-[10px] border border-line-strong bg-surface-raised p-3 text-left shadow-peek"
          >
            <span className="flex items-center justify-between gap-2">
              <span className="label">{shortSource(cite)}</span>
              <span className={cn('font-mono text-[0.56rem] uppercase', meta.color)}>
                {meta.relevanceLabel}
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
          </motion.span>,
          document.body,
        )}
    </span>
  );
}

import { useState } from 'react';
import { motion } from 'framer-motion';
import type { Citation } from '../lib/types';
import { useCitations } from './citationContext';
import { tierOf } from '../lib/tiers';
import { cn } from '../lib/utils';

/*
  The References section — set as a numbered bibliography with hanging
  indents, the authentic close of a journal article. Each entry highlights
  in sync with its in-text superscript and expands to show the grounded
  DiPiro passage it was retrieved from.
*/

export function References({ citations }: { citations: Citation[] }) {
  if (!citations.length) return null;
  return (
    <section className="mt-10">
      <div className="rule-hair mb-3 flex items-baseline gap-3 pt-2">
        <h3 className="sec !tracking-[0.22em] text-ink">References</h3>
        <span className="ident">{citations.length} cited · DiPiro 12e · Cohere-reranked</span>
      </div>
      <ol className="space-y-2.5">
        {citations.map((c, i) => (
          <ReferenceItem key={c.id} cite={c} index={i} />
        ))}
      </ol>
    </section>
  );
}

function ReferenceItem({ cite, index }: { cite: Citation; index: number }) {
  const { active, setActive } = useCitations();
  const [open, setOpen] = useState(false);
  const meta = tierOf(cite.tier);
  const isActive = active === cite.marker;

  return (
    <motion.li
      id={`cite-card-${cite.id}`}
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.05 * index, duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
      onMouseEnter={() => setActive(cite.marker)}
      onMouseLeave={() => setActive(null)}
      className={cn(
        'relative pl-8 transition-colors',
        isActive && 'bg-accent/[0.06]',
      )}
    >
      {/* Hanging marker */}
      <span
        className={cn(
          'absolute left-0 top-0 font-mono text-[0.72rem] tabular-nums',
          isActive ? 'text-accent' : 'text-ink-soft',
        )}
      >
        {cite.marker}.
      </span>

      <p className="font-prose text-[0.86rem] leading-snug text-ink-soft">
        <Bibliographic cite={cite} />{' '}
        <span className="ident">
          rel. {cite.relevance.toFixed(2)} · {meta.label}
        </span>{' '}
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          className="font-mono text-[0.6rem] uppercase tracking-[0.08em] text-accent underline-offset-2 hover:underline"
        >
          {open ? 'hide passage' : 'view passage'}
        </button>
      </p>

      <motion.div
        initial={false}
        animate={{ height: open ? 'auto' : 0, opacity: open ? 1 : 0 }}
        transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
        className="overflow-hidden"
      >
        <blockquote className="my-2 border-l-2 border-accent/40 pl-3 font-prose text-[0.82rem] italic leading-snug text-ink-soft">
          {cite.snippet}
        </blockquote>
      </motion.div>
    </motion.li>
  );
}

/* Renders each source in its own bibliographic house style. */
function Bibliographic({ cite }: { cite: Citation }) {
  if (cite.book === 'rxprep') {
    return (
      <>
        <span className="text-ink">RxPrep.</span>{' '}
        <em className="italic">NAPLEX Course Book.</em> UWorld, 2025. {cite.page}.
      </>
    );
  }
  if (cite.book === 'dipiro' || /dipiro/i.test(cite.source)) {
    return (
      <>
        <span className="text-ink">DiPiro JT, et al.</span>{' '}
        <em className="italic">Pharmacotherapy: A Pathophysiologic Approach.</em> 12th ed.{' '}
        {cite.section}. {cite.page}.
      </>
    );
  }
  return (
    <>
      <em className="italic text-ink">{cite.source}.</em> {cite.section}. {cite.page}.
    </>
  );
}

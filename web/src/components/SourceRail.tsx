import { AnimatePresence, motion } from 'framer-motion';
import type { Citation } from '../lib/types';
import { useCitations } from './citationContext';
import { tierOf } from '../lib/tiers';
import { cn } from '../lib/utils';

/*
  The source rail — the evidence behind a reply, folded into a row of chips
  instead of a bibliography. Each chip names its book and page; opening one
  slides out the retrieved passage itself with its rerank score. Inline
  citation markers drive the same rail, so clicking a superscript in the
  prose opens the exact passage that claim rests on.
*/

const ease = [0.22, 1, 0.36, 1] as const;

export function shortSource(c: Citation): string {
  if (c.book === 'rxprep') return 'RxPrep';
  if (c.book === 'dipiro' || /dipiro/i.test(c.source)) return 'DiPiro 12e';
  return c.source.split(',')[0];
}

export function SourceRail({ citations }: { citations: Citation[] }) {
  const { active, setActive, opened, setOpened } = useCitations();
  if (!citations.length) return null;

  const openCite = citations.find((c) => c.marker === opened) ?? null;

  return (
    <div className="mt-3">
      <motion.div
        initial="hidden"
        animate="show"
        variants={{ show: { transition: { staggerChildren: 0.045 } } }}
        className="flex flex-wrap gap-1.5"
      >
        {citations.map((c) => {
          const isOpen = opened === c.marker;
          const isActive = active === c.marker;
          const meta = tierOf(c.tier);
          return (
            <motion.button
              key={c.id}
              type="button"
              variants={{
                hidden: { opacity: 0, y: 6 },
                show: { opacity: 1, y: 0, transition: { duration: 0.35, ease } },
              }}
              whileHover={{ y: -1 }}
              onMouseEnter={() => setActive(c.marker)}
              onMouseLeave={() => setActive(null)}
              onClick={() => setOpened(isOpen ? null : c.marker)}
              aria-expanded={isOpen}
              className={cn(
                'group inline-flex items-center gap-2 rounded-full border py-1 pl-1 pr-3 transition-colors duration-200',
                isOpen
                  ? 'border-accent/50 bg-accent/[0.09]'
                  : isActive
                    ? 'border-line-strong bg-surface'
                    : 'border-line bg-surface/50 hover:border-line-strong',
              )}
            >
              <span
                className={cn(
                  'grid h-5 w-5 place-items-center rounded-full font-mono text-[0.6rem] tabular-nums transition-colors',
                  isOpen ? 'bg-accent text-page' : 'bg-line/70 text-ink-soft',
                )}
              >
                {c.marker}
              </span>
              <span className="font-mono text-[0.6rem] tracking-tight text-ink">
                {shortSource(c)}
              </span>
              <span className="font-mono text-[0.58rem] text-ink-faint">{c.page}</span>
              <span
                className={cn('h-1.5 w-1.5 rounded-full', meta.tint)}
                title={meta.label}
                aria-hidden
              />
            </motion.button>
          );
        })}
      </motion.div>

      <AnimatePresence initial={false} mode="wait">
        {openCite && (
          <motion.div
            key={openCite.id}
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.3, ease }}
            className="overflow-hidden"
          >
            <Passage cite={openCite} />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function Passage({ cite }: { cite: Citation }) {
  const meta = tierOf(cite.tier);
  return (
    <figure className="mt-2 rounded-[10px] border border-line bg-surface/60 p-3.5">
      <figcaption className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
        <span className="font-prose text-[0.82rem] italic text-ink">{cite.source}</span>
        <span className="font-mono text-[0.6rem] text-ink-faint">
          {cite.section} · {cite.page}
        </span>
        <span className={cn('ml-auto font-mono text-[0.58rem] uppercase tracking-[0.1em]', meta.color)}>
          {meta.label}
        </span>
      </figcaption>

      <blockquote className="mt-2.5 border-l-2 border-accent/45 pl-3 font-prose text-[0.88rem] italic leading-relaxed text-ink-soft">
        {cite.snippet}
      </blockquote>

      <div className="mt-3 flex items-center gap-2">
        <span className="label">Rerank</span>
        <span className="h-[3px] flex-1 overflow-hidden rounded-full bg-line">
          <motion.span
            className="block h-full rounded-full bg-accent/75"
            initial={{ scaleX: 0 }}
            animate={{ scaleX: cite.relevance }}
            style={{ originX: 0 }}
            transition={{ duration: 0.7, ease, delay: 0.1 }}
          />
        </span>
        <span className="font-mono text-[0.6rem] tabular-nums text-ink-faint">
          {cite.relevance.toFixed(2)}
        </span>
      </div>
    </figure>
  );
}

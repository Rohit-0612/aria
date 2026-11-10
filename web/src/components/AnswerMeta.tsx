import type { ReactNode } from 'react';
import { motion } from 'framer-motion';
import type { AssistantMessage } from '../lib/types';
import { tierOf } from '../lib/tiers';
import { VerdictStamp } from './VerdictStamp';
import { CopyButton } from './CopyButton';
import { useCitations } from './citationContext';
import { Icon } from './Icon';
import { Roll } from './fx';
import { cn } from '../lib/utils';

/*
  The footing of a reply: the Judge's verdict stamped beside it, the count
  of grounded sources, and copy. It arrives after the prose has landed — the
  stamp first, with a thump, the rest stepping in behind it.
*/

const ease = [0.22, 1, 0.36, 1] as const;

const item = {
  hidden: { opacity: 0, y: 6 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease } },
};

export function AnswerMeta({ message }: { message: AssistantMessage }) {
  const { railOpen, setRailOpen } = useCitations();
  const count = message.citations.length;

  // Last line of defence. A failed turn must never reach this component,
  // but if one ever does, it leaves without a certainty claim attached.
  if (message.phase === 'failed') return null;
  // A refusal is not an answer: there is nothing to grade and nothing to cite.
  if (message.outOfScope) return null;

  // `null` tier means the Judge never graded this answer: the stamp then says
  // "Not adjudicated" rather than inventing a verdict. The answer and its
  // citations are real, only the adjudication is missing.
  const meta = message.evidenceTier ? tierOf(message.evidenceTier) : null;
  const adjudicated = message.confidence !== null;

  return (
    <motion.div
      initial="hidden"
      animate="show"
      variants={{ show: { transition: { staggerChildren: 0.06, delayChildren: 0.1 } } }}
      className="mt-5 flex flex-wrap items-center gap-x-2 gap-y-2 border-t border-rule/40 pt-3.5"
    >
      <span className="group relative mr-1.5 outline-none" tabIndex={0}>
        <VerdictStamp tier={message.evidenceTier} confidence={message.confidence} />
        <Tip>
          {adjudicated
            ? (meta?.gloss ?? 'Independently adjudicated for groundedness and relevance')
            : 'The Judge was unavailable — this answer carries no confidence score'}
        </Tip>
      </span>

      {/* Sources */}
      {count > 0 && (
        <motion.span variants={item}>
          <button
            type="button"
            onClick={() => setRailOpen((v) => !v)}
            aria-expanded={railOpen}
            className={cn('chip gap-2', railOpen && '!border-accent/60 !bg-accent/[0.08] !text-ink')}
          >
            <Icon name="book" size={11} className={railOpen ? 'text-accent' : 'text-ink-faint'} />
            <Roll>{`${count} source${count > 1 ? 's' : ''}`}</Roll>
            <motion.span
              animate={{ rotate: railOpen ? 90 : 0 }}
              transition={{ duration: 0.22, ease }}
              className="text-ink-faint"
            >
              <Icon name="chevron" size={11} />
            </motion.span>
          </button>
        </motion.span>
      )}

      <motion.span variants={item} className="ml-auto">
        <CopyButton text={plainCitations(message.content)} />
      </motion.span>
    </motion.div>
  );
}

/** Copied text reads `[1, 3]` rather than the wire format `[[1]][[3]]`. */
function plainCitations(content: string): string {
  return content
    .replace(/\]\]\s*\[\[/g, ', ')
    .replace(/\[\[(\d+(?:\s*,\s*\d+)*)\]\]/g, '[$1]');
}

/** A hairline tooltip that appears on hover or keyboard focus. */
function Tip({ children }: { children: ReactNode }) {
  return (
    <span
      role="tooltip"
      className="pointer-events-none absolute bottom-[calc(100%+7px)] left-1/2 z-20 w-max max-w-[15rem] -translate-x-1/2 translate-y-1 rounded-[2px] border border-rule/50 bg-surface-raised px-2.5 py-1.5 text-center font-mono text-[0.58rem] leading-relaxed text-ink-soft opacity-0 shadow-peek transition-all duration-200 group-hover:translate-y-0 group-hover:opacity-100 group-focus-within:translate-y-0 group-focus-within:opacity-100"
    >
      {children}
    </span>
  );
}

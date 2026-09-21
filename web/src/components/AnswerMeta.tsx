import type { ReactNode } from 'react';
import { motion } from 'framer-motion';
import type { AssistantMessage } from '../lib/types';
import { tierOf } from '../lib/tiers';
import { ConfidenceGauge } from './ConfidenceGauge';
import { CopyButton } from './CopyButton';
import { useCitations } from './citationContext';
import { Icon } from './Icon';
import { cn } from '../lib/utils';

/*
  The footing of a reply — everything the old margin box carried, compressed
  into one quiet row of instruments: GRADE certainty, the Judge's score, the
  count of grounded sources, and copy. It arrives after the prose has landed,
  each element stepping in a beat behind the last.
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

  // `null` tier means the Judge never graded this answer. Render the row
  // without a GRADE chip rather than inventing one — the answer and its
  // citations are real, only the adjudication is missing.
  const meta = message.evidenceTier ? tierOf(message.evidenceTier) : null;
  const adjudicated = message.confidence !== null;

  return (
    <motion.div
      initial="hidden"
      animate="show"
      variants={{ show: { transition: { staggerChildren: 0.06, delayChildren: 0.1 } } }}
      className="mt-5 flex flex-wrap items-center gap-x-2 gap-y-2 border-t border-line/70 pt-3"
    >
      {/* GRADE certainty — only when the Judge actually graded the answer */}
      {meta && (
        <motion.span variants={item} className="group relative">
          <span className="chip !cursor-default gap-2">
            <span className="flex items-end gap-[2px]" aria-hidden>
              {[0, 1, 2].map((i) => (
                <motion.span
                  key={i}
                  initial={{ scaleY: 0.15 }}
                  animate={{ scaleY: 1 }}
                  transition={{ delay: 0.15 + i * 0.07, duration: 0.35, ease }}
                  style={{ originY: 1 }}
                  className={cn(
                    'w-[3px] rounded-[1px]',
                    i < meta.segments ? meta.tint : 'bg-line-strong/60',
                    i === 0 && 'h-1.5',
                    i === 1 && 'h-2.5',
                    i === 2 && 'h-3.5',
                  )}
                />
              ))}
            </span>
            <span className={meta.color}>{meta.label}</span>
          </span>
          <Tip>{meta.gloss}</Tip>
        </motion.span>
      )}

      {/* Judge score, or an explicit statement that there isn't one */}
      {adjudicated && message.confidence !== null ? (
        message.confidence > 0 && (
          <motion.span variants={item} className="group relative">
            <span className="chip !cursor-default gap-2 !py-0.5 !pl-1">
              <ConfidenceGauge value={message.confidence} size={20} showValue={false} />
              <span className="tabular-nums text-ink">{message.confidence.toFixed(2)}</span>
              <span className="text-ink-faint">judge</span>
            </span>
            <Tip>Independently adjudicated for groundedness and relevance</Tip>
          </motion.span>
        )
      ) : (
        <motion.span variants={item} className="group relative">
          <span className="chip !cursor-default gap-2 !border-oxblood/40 !text-oxblood">
            <Icon name="caution" size={11} />
            <span>Not adjudicated</span>
          </span>
          <Tip>The Judge was unavailable — this answer carries no confidence score</Tip>
        </motion.span>
      )}

      {/* Sources */}
      {count > 0 && (
        <motion.span variants={item}>
          <button
            type="button"
            onClick={() => setRailOpen((v) => !v)}
            aria-expanded={railOpen}
            className={cn(
              'chip gap-2',
              railOpen && '!border-accent/50 !bg-accent/[0.08] !text-ink',
            )}
          >
            <Icon name="book" size={11} className={railOpen ? 'text-accent' : 'text-ink-faint'} />
            <span>
              {count} source{count > 1 ? 's' : ''}
            </span>
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
        <CopyButton text={message.content} />
      </motion.span>
    </motion.div>
  );
}

/** A hairline tooltip that appears on hover or keyboard focus. */
function Tip({ children }: { children: ReactNode }) {
  return (
    <span
      role="tooltip"
      className="pointer-events-none absolute bottom-[calc(100%+7px)] left-1/2 z-20 w-max max-w-[15rem] -translate-x-1/2 translate-y-1 rounded-[6px] border border-line-strong bg-surface-raised px-2.5 py-1.5 text-center font-mono text-[0.58rem] leading-relaxed text-ink-soft opacity-0 shadow-peek transition-all duration-200 group-hover:translate-y-0 group-hover:opacity-100 group-focus-within:translate-y-0 group-focus-within:opacity-100"
    >
      {children}
    </span>
  );
}

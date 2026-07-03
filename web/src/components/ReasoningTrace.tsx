import { useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import type { AgentStep } from '../lib/types';
import { Icon, type IconName } from './Icon';
import { cn } from '../lib/utils';

/*
  The reasoning trace — ARIA's signature moment.
  The four LangGraph nodes are drawn as a vertical signal chain. A luminous
  filament travels the rail as work advances; the active node breathes; each
  completed node prints its instrument readout (chunks reranked, sources
  cited, confidence). Once complete it collapses to a single ledger line that
  can be re-expanded — the reasoning stays inspectable, never noisy.
*/

const ICONS: Record<AgentStep['id'], IconName> = {
  guardrail: 'guardrail',
  navigator: 'navigator',
  generator: 'generator',
  judge: 'judge',
};

interface Props {
  steps: AgentStep[];
  /** When the whole turn is complete, start collapsed. */
  complete: boolean;
}

export function ReasoningTrace({ steps, complete }: Props) {
  const [open, setOpen] = useState(!complete);
  // Keep it expanded while in flight regardless of toggle.
  const inFlight = steps.some((s) => s.status === 'active' || s.status === 'pending');
  const expanded = inFlight || open;

  const done = steps.filter((s) => s.status === 'done');
  const total = done.reduce((a, s) => a + (s.durationMs ?? 0), 0);
  const progress = steps.length ? done.length / steps.length : 0;

  return (
    <div className="select-none">
      <button
        type="button"
        onClick={() => !inFlight && setOpen((v) => !v)}
        disabled={inFlight}
        aria-expanded={expanded}
        className={cn(
          'group flex w-full items-center gap-2.5 text-left',
          !inFlight && 'cursor-pointer',
        )}
      >
        <span className="label !text-[0.6rem]">Reasoning trace</span>
        <span className="h-px flex-1 bg-line" />
        {inFlight ? (
          <LiveDot />
        ) : (
          <span className="font-mono text-[0.62rem] text-ink-faint">
            {(total / 1000).toFixed(1)}s · {done.length}/{steps.length}
          </span>
        )}
        {!inFlight && (
          <motion.span
            animate={{ rotate: expanded ? 90 : 0 }}
            transition={{ duration: 0.2 }}
            className="text-ink-faint"
          >
            <Icon name="chevron" size={13} />
          </motion.span>
        )}
      </button>

      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }}
            className="overflow-hidden"
          >
            <ol className="relative mt-3 pl-[26px]">
              {/* The rail + traveling filament */}
              <span className="absolute left-[11px] top-1 bottom-1 w-px bg-line" aria-hidden />
              <motion.span
                aria-hidden
                className="absolute left-[11px] top-1 w-px origin-top bg-accent"
                style={{ bottom: 4 }}
                initial={false}
                animate={{ scaleY: progress }}
                transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
              />
              {steps.map((step) => (
                <TraceNode key={step.id} step={step} />
              ))}
            </ol>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function TraceNode({ step }: { step: AgentStep }) {
  const active = step.status === 'active';
  const isDone = step.status === 'done';
  const skipped = step.status === 'skipped';

  return (
    <li className="relative mb-3 last:mb-0">
      {/* Node marker sits over the rail */}
      <span className="absolute -left-[26px] top-0 grid h-[23px] w-[23px] place-items-center">
        {active && (
          <motion.span
            className="absolute inset-0 rounded-full bg-accent/20"
            animate={{ scale: [1, 1.5, 1], opacity: [0.6, 0, 0.6] }}
            transition={{ duration: 1.6, repeat: Infinity, ease: 'easeInOut' }}
          />
        )}
        <span
          className={cn(
            'relative grid h-[23px] w-[23px] place-items-center rounded-full border bg-surface transition-colors',
            active && 'border-accent text-accent',
            isDone && 'border-tier-strong/60 text-tier-strong',
            skipped && 'border-line text-ink-faint/60',
            step.status === 'pending' && 'border-line text-ink-faint',
          )}
        >
          {isDone ? (
            <motion.span
              initial={{ scale: 0, rotate: -20 }}
              animate={{ scale: 1, rotate: 0 }}
              transition={{ type: 'spring', stiffness: 500, damping: 22 }}
            >
              <Icon name="check" size={12} strokeWidth={2.2} />
            </motion.span>
          ) : (
            <Icon name={ICONS[step.id]} size={12} />
          )}
        </span>
      </span>

      <div className="flex items-baseline gap-2">
        <span
          className={cn(
            'font-mono text-[0.7rem] font-medium uppercase tracking-[0.08em]',
            active ? 'text-accent' : skipped ? 'text-ink-faint/70' : 'text-ink',
          )}
        >
          {step.label}
        </span>
        {step.metric && (isDone || skipped) && (
          <motion.span
            initial={{ opacity: 0, x: -4 }}
            animate={{ opacity: 1, x: 0 }}
            className="font-mono text-[0.62rem] text-ink-faint"
          >
            {step.metric}
          </motion.span>
        )}
        {active && <ActiveTicker />}
      </div>
      <p
        className={cn(
          'mt-0.5 font-prose text-[0.82rem] leading-snug',
          skipped ? 'text-ink-faint/70' : 'text-ink-soft',
        )}
      >
        {step.detail}
      </p>
    </li>
  );
}

function ActiveTicker() {
  return (
    <span className="inline-flex items-center gap-[3px]" aria-hidden>
      {[0, 1, 2].map((i) => (
        <motion.span
          key={i}
          className="h-1 w-1 rounded-full bg-accent"
          animate={{ opacity: [0.25, 1, 0.25] }}
          transition={{ duration: 1.1, repeat: Infinity, delay: i * 0.18 }}
        />
      ))}
    </span>
  );
}

function LiveDot() {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="relative flex h-1.5 w-1.5">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent/70" />
        <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-accent" />
      </span>
      <span className="font-mono text-[0.6rem] uppercase tracking-[0.12em] text-accent">
        working
      </span>
    </span>
  );
}

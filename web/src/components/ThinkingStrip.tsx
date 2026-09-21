import { useEffect, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import type { AgentStep } from '../lib/types';
import { Icon, type IconName } from './Icon';
import { cn } from '../lib/utils';

/*
  The thinking strip — one line of live status above the answer.

  While the graph runs it names the node that is working and cross-fades to
  the next one, with the four-node chain open beneath it so you can watch
  retrieval and adjudication happen. The moment the answer is complete the
  chain folds itself away into a single receipt line — "Reasoned in 4.2s ·
  248 → 6 chunks" — that can be reopened. The reasoning stays inspectable
  without ever competing with the reply.
*/

const ICONS: Record<AgentStep['id'], IconName> = {
  guardrail: 'guardrail',
  navigator: 'navigator',
  generator: 'generator',
  judge: 'judge',
};

const ease = [0.22, 1, 0.36, 1] as const;

interface Props {
  steps: AgentStep[];
  /** True once the whole turn has finished streaming. */
  complete: boolean;
}

export function ThinkingStrip({ steps, complete }: Props) {
  const [userOpen, setUserOpen] = useState(false);
  const working = !complete && steps.some((s) => s.status === 'active' || s.status === 'pending');
  const expanded = working || userOpen;

  // Once the turn settles, fold the chain back up.
  useEffect(() => {
    if (complete) setUserOpen(false);
  }, [complete]);

  const active = steps.find((s) => s.status === 'active');
  const done = steps.filter((s) => s.status === 'done');
  const anyFailed = steps.some((s) => s.status === 'failed');
  const elapsed = done.reduce((a, s) => a + (s.durationMs ?? 0), 0);
  const progress = steps.length ? done.length / steps.length : 0;
  const receipt = done.find((s) => s.id === 'navigator')?.metric;

  return (
    <div className="select-none">
      <button
        type="button"
        onClick={() => !working && setUserOpen((v) => !v)}
        disabled={working}
        aria-expanded={expanded}
        aria-label={working ? 'ARIA is reasoning' : 'Show reasoning trace'}
        className={cn(
          'group -ml-1.5 flex max-w-full items-center gap-2 rounded-full px-1.5 py-1 text-left transition-colors',
          !working && 'hover:bg-line/40',
        )}
      >
        <PulseDot live={working} />

        <span className="min-w-0 flex-1 overflow-hidden">
          <AnimatePresence mode="wait" initial={false}>
            <motion.span
              key={working ? (active?.id ?? 'start') : 'receipt'}
              initial={{ opacity: 0, y: 5 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -5 }}
              transition={{ duration: 0.24, ease }}
              className="block truncate font-mono text-[0.66rem] uppercase tracking-[0.12em]"
            >
              {working ? (
                <span className="shimmer">
                  {active ? `${active.label} — ${active.detail}` : 'Opening the consultation'}
                </span>
              ) : (
                <span className={anyFailed ? 'text-oxblood/80' : 'text-ink-faint'}>
                  {anyFailed ? 'Stopped after ' : 'Reasoned in '}
                  {(elapsed / 1000).toFixed(1)}s
                  {/* The retrieval figures need room a phone doesn't have. */}
                  {receipt && (
                    <span className="hidden text-ink-faint/70 sm:inline"> · {receipt}</span>
                  )}
                </span>
              )}
            </motion.span>
          </AnimatePresence>
        </span>

        {!working && (
          <motion.span
            animate={{ rotate: expanded ? 90 : 0 }}
            transition={{ duration: 0.22, ease }}
            className="shrink-0 text-ink-faint/70 transition-colors group-hover:text-ink-soft"
          >
            <Icon name="chevron" size={12} />
          </motion.span>
        )}
      </button>

      <AnimatePresence initial={false}>
        {expanded && steps.length > 0 && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.36, ease }}
            className="overflow-hidden"
          >
            <ol className="relative mb-1 mt-2.5 pl-[26px]">
              <span className="absolute bottom-2 left-[9px] top-2 w-px bg-line" aria-hidden />
              <motion.span
                aria-hidden
                className="absolute bottom-2 left-[9px] top-2 w-px origin-top bg-accent/80"
                initial={false}
                animate={{ scaleY: progress }}
                transition={{ duration: 0.55, ease }}
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
  const isFailed = step.status === 'failed';

  return (
    <li className="relative mb-2.5 last:mb-0">
      <span className="absolute -left-[26px] top-[1px] grid h-[19px] w-[19px] place-items-center">
        {active && (
          <motion.span
            className="absolute inset-0 rounded-full bg-accent/25"
            animate={{ scale: [1, 1.6, 1], opacity: [0.7, 0, 0.7] }}
            transition={{ duration: 1.6, repeat: Infinity, ease: 'easeInOut' }}
          />
        )}
        <span
          className={cn(
            'relative grid h-[19px] w-[19px] place-items-center rounded-full border bg-page transition-colors',
            active && 'border-accent text-accent',
            isDone && 'border-tier-strong/60 text-tier-strong',
            isFailed && 'border-oxblood/70 text-oxblood',
            skipped && 'border-line text-ink-faint/60',
            step.status === 'pending' && 'border-line text-ink-faint/70',
          )}
        >
          {isFailed ? (
            <Icon name="close" size={9} strokeWidth={2.4} />
          ) : isDone ? (
            <motion.span
              initial={{ scale: 0, rotate: -25 }}
              animate={{ scale: 1, rotate: 0 }}
              transition={{ type: 'spring', stiffness: 520, damping: 22 }}
            >
              <Icon name="check" size={10} strokeWidth={2.4} />
            </motion.span>
          ) : (
            <Icon name={ICONS[step.id]} size={10} />
          )}
        </span>
      </span>

      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
        <span
          className={cn(
            'font-mono text-[0.63rem] uppercase tracking-[0.12em]',
            active
              ? 'text-accent'
              : isFailed
                ? 'text-oxblood'
                : skipped
                  ? 'text-ink-faint/70'
                  : 'text-ink',
          )}
        >
          {step.label}
        </span>
        <span
          className={cn(
            'font-prose text-[0.8rem] leading-snug',
            isFailed ? 'text-oxblood/90' : skipped ? 'text-ink-faint/70' : 'text-ink-soft',
          )}
        >
          {step.detail}
        </span>
        {step.metric && (isDone || skipped || isFailed) && (
          <motion.span
            initial={{ opacity: 0, x: -4 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.3, ease }}
            className="font-mono text-[0.58rem] tabular-nums text-ink-faint"
          >
            {step.metric}
          </motion.span>
        )}
      </div>
    </li>
  );
}

function PulseDot({ live }: { live: boolean }) {
  return (
    <span className="relative flex h-1.5 w-1.5 shrink-0" aria-hidden>
      {live && (
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent/70" />
      )}
      <span
        className={cn(
          'relative inline-flex h-1.5 w-1.5 rounded-full',
          live ? 'bg-accent' : 'bg-line-strong',
        )}
      />
    </span>
  );
}

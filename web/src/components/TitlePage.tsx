import { useEffect } from 'react';
import { motion } from 'framer-motion';

/*
  The cover — a title page shown when the journal is first opened.
  The colophon draws itself in ink, the title rises off the baseline
  letter by letter, the masthead rules unroll, and then the cover
  lifts away to reveal the consultation page beneath.
*/

interface Props {
  reduced: boolean;
  onDone: () => void;
}

const HOLD_MS = 3400;
const HOLD_REDUCED_MS = 1200;
const settle = [0.22, 1, 0.36, 1] as const;

export function TitlePage({ reduced, onDone }: Props) {
  useEffect(() => {
    const t = setTimeout(onDone, reduced ? HOLD_REDUCED_MS : HOLD_MS);
    return () => clearTimeout(t);
  }, [reduced, onDone]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Enter' || e.key === 'Escape' || e.key === ' ') onDone();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onDone]);

  // One timing helper: everything snaps into place under reduced motion.
  const t = (duration: number, delay = 0) =>
    reduced ? { duration: 0 } : { duration, delay, ease: settle };

  return (
    <motion.div
      role="presentation"
      onClick={onDone}
      className="fixed inset-0 z-50 flex cursor-pointer flex-col items-center justify-center overflow-hidden bg-desk"
      style={{
        backgroundImage:
          'linear-gradient(hsl(var(--ink) / 0.02) 1px, transparent 1px), linear-gradient(90deg, hsl(var(--ink) / 0.02) 1px, transparent 1px)',
        backgroundSize: '26px 26px',
      }}
      exit={
        reduced
          ? { opacity: 0, transition: { duration: 0.15 } }
          : { opacity: 0, y: '-4%', transition: { duration: 0.65, ease: settle } }
      }
    >
      {/* Cover frame — the hairline border of a bound journal. */}
      <motion.div
        aria-hidden="true"
        className="pointer-events-none absolute inset-3 border border-rule/25 sm:inset-6"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={t(1.2, 0.9)}
      />

      <div className="flex flex-col items-center px-6 text-center">
        {/* Colophon — drawn stroke by stroke. */}
        <svg
          width="84"
          height="84"
          viewBox="0 0 96 96"
          fill="none"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
          className="mb-6"
        >
          <motion.circle
            cx="48"
            cy="48"
            r="43"
            stroke="hsl(var(--rule) / 0.8)"
            strokeWidth="1.5"
            initial={{ pathLength: reduced ? 1 : 0 }}
            animate={{ pathLength: 1 }}
            transition={t(1.1, 0.1)}
          />
          <motion.circle
            cx="48"
            cy="48"
            r="37"
            stroke="hsl(var(--rule) / 0.35)"
            strokeWidth="1"
            initial={{ pathLength: reduced ? 1 : 0 }}
            animate={{ pathLength: 1 }}
            transition={t(1.1, 0.25)}
          />
          <motion.path
            d="M31.5 63L48 22.5 64.5 63"
            stroke="hsl(var(--accent))"
            strokeWidth="2.4"
            initial={{ pathLength: reduced ? 1 : 0, opacity: reduced ? 1 : 0 }}
            animate={{ pathLength: 1, opacity: 1 }}
            transition={t(0.9, 0.55)}
          />
          <motion.path
            d="M38 49.5h20"
            stroke="hsl(var(--accent))"
            strokeWidth="2.4"
            initial={{ pathLength: reduced ? 1 : 0, opacity: reduced ? 1 : 0 }}
            animate={{ pathLength: 1, opacity: 1 }}
            transition={t(0.5, 1.15)}
          />
        </svg>

        {/* Title — letters rise off the baseline like set type. */}
        <h1
          className="font-display text-[4.4rem] font-semibold leading-none tracking-[-0.03em] text-ink sm:text-[7rem]"
          aria-label="ARIA"
        >
          {['A', 'R', 'I', 'A'].map((ch, i) => (
            <span key={i} className="inline-block overflow-hidden align-bottom">
              <motion.span
                className="inline-block"
                initial={reduced ? false : { y: '110%' }}
                animate={{ y: 0 }}
                transition={t(0.8, 0.5 + i * 0.09)}
              >
                {ch}
              </motion.span>
            </span>
          ))}
        </h1>

        {/* Masthead rules unroll from the center. */}
        <motion.div
          className="mt-6 w-56 sm:w-72"
          initial={reduced ? false : { scaleX: 0 }}
          animate={{ scaleX: 1 }}
          transition={t(0.8, 1.15)}
        >
          <div className="rule-double" />
          <div className="rule-hair mt-[3px]" />
        </motion.div>

        <motion.p
          className="mt-5 font-prose text-[1rem] italic text-ink-soft sm:text-[1.15rem]"
          initial={reduced ? false : { opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={t(0.7, 1.45)}
        >
          The Journal of Evidence-Grounded Pharmacotherapy
        </motion.p>

        <motion.p
          className="mt-3 font-mono text-[0.6rem] uppercase tracking-[0.22em] text-ink-faint"
          initial={reduced ? false : { opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={t(0.9, 1.75)}
        >
          Retrieval · Reranking · Adjudication
        </motion.p>
      </div>

      <motion.span
        className="absolute bottom-8 font-mono text-[0.56rem] uppercase tracking-[0.18em] text-ink-faint/70 sm:bottom-10"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={t(0.9, 2.1)}
      >
        Tap anywhere to enter
      </motion.span>
    </motion.div>
  );
}

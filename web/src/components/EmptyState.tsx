import { useMemo } from 'react';
import { motion } from 'framer-motion';
import { PROMPT_SEEDS } from '../lib/mockData';
import { CountUp, Doodle, RiseChars } from './fx';
import { Halftone } from './Halftone';

/*
  The front page of the consultation.

  A dateline, the nameplate printed in reverse on an ink slab, a standfirst
  that says what ARIA does and on what evidence, a strip of figures from the
  evaluation, and "In this issue": four consults set as headlines. The
  letters of the nameplate rise and the figures count up as the curtain
  tears away; the whole page lifts off the moment a question is asked.
*/

const expo = [0.19, 1, 0.22, 1] as const;

/* Figures from the README's evaluation — keep them in step with it. */
const STATS = [
  { value: 27104, decimals: 0, label: 'passages indexed' },
  { value: 2, decimals: 0, label: 'reference texts' },
  { value: 4, decimals: 0, label: 'agents per answer' },
  { value: 0.9, decimals: 2, label: 'groundedness · eval' },
];

interface Props {
  onPick: (query: string) => void;
  /** True once the cover has lifted, so the page animates in view. */
  play: boolean;
  reduced: boolean;
}

export function EmptyState({ onPick, play, reduced }: Props) {
  const date = useMemo(
    () =>
      new Date().toLocaleDateString('en-GB', {
        weekday: 'long',
        day: 'numeric',
        month: 'long',
        year: 'numeric',
      }),
    [],
  );

  const rise = (delay: number) =>
    reduced
      ? { initial: false as const, animate: { opacity: 1, y: 0 } }
      : {
          initial: { opacity: 0, y: 26 },
          animate: play ? { opacity: 1, y: 0 } : { opacity: 0, y: 26 },
          transition: { duration: 1.1, delay, ease: expo },
        };

  return (
    <motion.div
      key="empty"
      exit={{ opacity: 0, y: -24, filter: 'blur(3px)' }}
      transition={{ duration: 0.4, ease: expo }}
      /* `safe center` keeps the nameplate reachable when the page is taller
         than a short phone viewport — plain centering clips the top. */
      className="flex w-full flex-1 flex-col py-1 [justify-content:safe_center] sm:py-3"
    >
      {/* Dateline */}
      <motion.div
        {...rise(0.15)}
        className="flex items-baseline justify-between gap-3 border-b border-rule pb-1.5 font-prose text-[0.74rem] leading-none text-ink-soft sm:text-[0.8rem]"
      >
        <span>{date}</span>
        <span className="hidden italic md:inline">The Consultation Ledger · Vol. 1</span>
        <span className="text-right">DiPiro 12e · RxPrep 2025</span>
      </motion.div>

      <div className="mt-3.5 grid gap-5 sm:mt-4 sm:grid-cols-[minmax(0,1fr)_190px]">
        <div className="min-w-0">
          {/* Nameplate, printed in reverse */}
          <h1 className="slab head overflow-hidden text-center text-[clamp(5.2rem,21vw,9.6rem)] leading-[0.8]">
            <span className="block px-4 pb-[0.02em] pt-[0.14em]">
              <RiseChars text="ARIA" play={play} delay={0.25} stagger={0.06} reduced={reduced} />
            </span>
          </h1>

          <motion.p
            {...rise(0.45)}
            className="head mt-3 text-[clamp(1.45rem,4.6vw,2.15rem)] leading-[0.92]"
          >
            Evidence-grounded <span className="text-ink-faint">&amp;</span> cited
          </motion.p>
          <motion.p
            {...rise(0.55)}
            className="mt-2 max-w-[34rem] text-balance font-prose text-[1rem] leading-[1.35] text-ink-soft sm:text-[1.08rem]"
          >
            Clinical pharmacotherapy answers written only from the textbooks — every claim cited
            to its printed page, every answer graded by an independent Judge.
          </motion.p>
        </div>

        {/* Plate */}
        <motion.figure {...rise(0.35)} className="hidden sm:block">
          <div className="relative aspect-[4/5] border border-rule bg-surface">
            <Halftone
              label="Halftone print of a capsule and a scored tablet"
              className="h-full w-full"
              fineness={62}
              play={play}
            />
            <span className="stamp absolute -right-3 -top-3 block h-[78px] w-[64px] rotate-[5deg] text-accent">
              <span className="stamp-in flex flex-col items-center justify-between py-1.5 text-center">
                <span className="font-mono text-[0.44rem] uppercase leading-none tracking-[0.1em]">Agents</span>
                <b className="head text-[1.9rem] leading-[0.8]">4</b>
                <span className="font-mono text-[0.44rem] uppercase leading-none tracking-[0.06em]">Per answer</span>
              </span>
            </span>
          </div>
          <figcaption className="mt-1.5 font-prose text-[0.74rem] italic leading-tight text-ink-soft">
            Fig. 1 — The evidence, printed in halftone.
          </figcaption>
        </motion.figure>
      </div>

      {/* Figures */}
      <motion.dl
        {...rise(0.6)}
        className="mt-5 grid grid-cols-2 border-t border-rule sm:mt-6 sm:grid-cols-4"
      >
        {STATS.map((s, i) => (
          <div
            key={s.label}
            className={
              'border-rule/40 pb-1 pt-2.5 sm:pt-3 ' +
              (i % 2 ? 'border-l pl-3 ' : '') +
              (i > 0 ? 'sm:border-l sm:pl-3.5 ' : '') +
              (i > 1 ? 'border-t sm:border-t-0' : '')
            }
          >
            <dt className="sr-only">{s.label}</dt>
            <dd className="head text-[1.9rem] leading-none sm:text-[2.2rem]">
              <CountUp value={s.value} decimals={s.decimals} play={play} reduced={reduced} ms={1800} />
            </dd>
            <dd aria-hidden className="mt-1 font-prose text-[0.78rem] italic leading-tight text-ink-soft">
              {s.label}
            </dd>
          </div>
        ))}
      </motion.dl>

      {/* In this issue */}
      <motion.div
        {...rise(0.7)}
        className="mt-5 flex items-center gap-3 border-t-2 border-rule pt-2 sm:mt-6"
      >
        <span className="head text-[0.95rem] leading-none">No. 01–04</span>
        <span className="font-prose text-[0.95rem] italic leading-none text-ink-soft">In this issue</span>
        <span className="h-px flex-1 bg-rule/30" />
        <span className="hidden font-mono text-[0.56rem] uppercase tracking-[0.14em] text-ink-faint sm:inline">
          Pick one to ask
        </span>
      </motion.div>

      <motion.ul
        initial={reduced ? false : 'hidden'}
        animate={play || reduced ? 'show' : 'hidden'}
        variants={{ show: { transition: { staggerChildren: 0.07, delayChildren: reduced ? 0 : 0.8 } } }}
        className="mt-1 grid sm:grid-cols-2 sm:gap-x-6"
      >
        {PROMPT_SEEDS.map((s, i) => (
          <motion.li
            key={s.id}
            variants={{
              hidden: { opacity: 0, y: 18 },
              show: { opacity: 1, y: 0, transition: { duration: 0.9, ease: expo } },
            }}
            className="border-b border-rule/25"
          >
            <button
              type="button"
              onClick={() => onPick(s.query)}
              data-cursor="Ask ↗"
              className="doodle-trigger group flex w-full flex-col items-start gap-1 py-2.5 text-left sm:py-3"
            >
              <span className="font-mono text-[0.58rem] uppercase tracking-[0.14em] text-ink-faint transition-colors group-hover:text-accent">
                {String(i + 1).padStart(2, '0')} · {s.topic}
              </span>
              <span className="doodle-host head text-[1.3rem] leading-[0.95] transition-colors group-hover:text-ink sm:text-[1.4rem]">
                {s.title}
                <Doodle />
              </span>
            </button>
          </motion.li>
        ))}
      </motion.ul>
    </motion.div>
  );
}

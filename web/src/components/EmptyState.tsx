import { motion } from 'framer-motion';
import { PROMPT_SEEDS } from '../lib/mockData';
import { Icon } from './Icon';

/*
  The opening of the consultation — the nameplate, one line on the method,
  and a short index of saved consults. Deliberately spare: whitespace does
  the rest. It lifts away the moment the first question is asked.
*/

const ease = [0.22, 1, 0.36, 1] as const;

export function EmptyState({ onPick }: { onPick: (query: string) => void }) {
  return (
    <motion.div
      key="empty"
      exit={{ opacity: 0, y: -18, filter: 'blur(3px)' }}
      transition={{ duration: 0.4, ease }}
      /* `safe center` keeps the nameplate reachable when the content is
         taller than a short phone viewport — plain centering clips the top. */
      className="mx-auto flex w-full max-w-xl flex-1 flex-col px-1 py-4 [justify-content:safe_center] sm:py-8"
    >
      {/* Nameplate */}
      <header className="flex flex-col items-center text-center">
        <motion.span
          initial={{ opacity: 0, scale: 0.85 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.7, ease }}
          className="mb-3 text-accent"
        >
          <Icon name="aria" size={28} strokeWidth={1.3} />
        </motion.span>

        <motion.h1
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.05, ease }}
          className="font-display text-[2.5rem] font-semibold leading-none tracking-[-0.03em] text-ink sm:text-[3.6rem]"
        >
          ARIA
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.14, ease }}
          className="mt-2 text-balance font-prose text-[0.88rem] italic text-ink-soft sm:mt-2.5 sm:text-[0.95rem]"
        >
          The Journal of Evidence-Grounded Pharmacotherapy
        </motion.p>

        <motion.div
          initial={{ scaleX: 0 }}
          animate={{ scaleX: 1 }}
          transition={{ duration: 0.8, delay: 0.2, ease }}
          className="mt-4 w-full sm:mt-6"
        >
          <div className="rule-double" />
          <div className="rule-hair mt-[3px]" />
        </motion.div>
      </header>

      {/* Epigraph — the journal's standing principle, not a feature list. The
          corpus and the pipeline announce themselves per answer, in the source
          rail and the instrument row, where a reader can actually check them. */}
      <motion.p
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.7, delay: 0.3, ease }}
        className="mt-5 text-balance text-center font-prose text-[0.98rem] italic leading-[1.7] text-ink-soft sm:mt-8 sm:text-[1.06rem] sm:leading-[1.75]"
      >
        Every claim carries its source. Every answer, its reasoning.
      </motion.p>

      {/* Saved consults */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.7, delay: 0.5, ease }}
        className="mt-6 flex items-center gap-4 sm:mt-9"
      >
        <span className="rule-hair flex-1" />
        <span className="sec text-accent">In this issue</span>
        <span className="rule-hair flex-1" />
      </motion.div>

      <motion.ul
        initial="hidden"
        animate="show"
        variants={{ show: { transition: { staggerChildren: 0.08, delayChildren: 0.58 } } }}
        className="mt-2"
      >
        {PROMPT_SEEDS.map((s, i) => (
          <motion.li
            key={s.id}
            variants={{
              hidden: { opacity: 0, y: 10 },
              show: { opacity: 1, y: 0, transition: { duration: 0.5, ease } },
            }}
            className="border-b border-line/70 last:border-b-0"
          >
            <button
              type="button"
              onClick={() => onPick(s.query)}
              className="group relative flex w-full items-baseline gap-3 py-3 pl-2 pr-1 text-left sm:gap-4 sm:py-3.5"
            >
              {/* A hairline runs in from the margin on hover. */}
              <span className="absolute inset-y-1 left-0 w-[2px] origin-top scale-y-0 bg-accent transition-transform duration-300 group-hover:scale-y-100" />
              <span className="w-5 shrink-0 text-right font-mono text-[0.66rem] tabular-nums text-ink-faint transition-colors group-hover:text-accent">
                {roman(i + 1)}
              </span>
              <span className="flex-1 font-prose text-[0.95rem] font-medium leading-snug text-ink transition-transform duration-300 group-hover:translate-x-0.5 sm:text-[0.99rem]">
                {s.title}
              </span>
              <span className="ident hidden shrink-0 sm:inline">{s.topic}</span>
              <span className="shrink-0 self-center text-accent opacity-0 transition-all duration-300 group-hover:translate-x-0.5 group-hover:opacity-100">
                <Icon name="send" size={13} />
              </span>
            </button>
          </motion.li>
        ))}
      </motion.ul>
    </motion.div>
  );
}

const ROMAN = ['', 'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII'];
const roman = (n: number) => ROMAN[n] ?? String(n);

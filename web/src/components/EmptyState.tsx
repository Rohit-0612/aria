import { motion } from 'framer-motion';
import { PROMPT_SEEDS } from '../lib/mockData';
import { Icon } from './Icon';

/*
  The opening page — deliberately spare. One epigraph stating the
  journal's method, then a small table of contents of selected queries.
  Whitespace does the rest.
*/

const ease = [0.22, 1, 0.36, 1] as const;

export function EmptyState({ onPick }: { onPick: (query: string) => void }) {
  return (
    <div className="mx-auto max-w-xl pb-6">
      {/* Epigraph */}
      <motion.p
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.7, delay: 0.15, ease }}
        className="text-center font-prose text-[1.05rem] italic leading-[1.8] text-ink-soft sm:text-[1.12rem]"
      >
        Every answer is retrieved, reranked, and adjudicated against{' '}
        <em className="text-ink">DiPiro&apos;s Pharmacotherapy</em> — you read the
        method and the references, not just the conclusion.
      </motion.p>

      {/* Section heading, flanked by hairlines */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.7, delay: 0.4, ease }}
        className="mt-10 flex items-center gap-4"
      >
        <span className="rule-hair flex-1" />
        <span className="sec text-accent">In this issue</span>
        <span className="rule-hair flex-1" />
      </motion.div>

      {/* Table of contents */}
      <motion.ul
        initial="hidden"
        animate="show"
        variants={{ show: { transition: { staggerChildren: 0.09, delayChildren: 0.5 } } }}
        className="mt-4"
      >
        {PROMPT_SEEDS.map((s, i) => (
          <motion.li
            key={s.id}
            variants={{
              hidden: { opacity: 0, y: 10 },
              show: { opacity: 1, y: 0, transition: { duration: 0.55, ease } },
            }}
            className="border-b border-line/70 last:border-b-0"
          >
            <button
              type="button"
              onClick={() => onPick(s.query)}
              className="group flex w-full items-baseline gap-4 py-4 text-left"
            >
              <span className="w-6 shrink-0 text-right font-mono text-[0.68rem] tabular-nums text-ink-faint transition-colors group-hover:text-accent">
                {roman(i + 1)}
              </span>
              <span className="flex-1 font-prose text-[1rem] font-medium leading-snug text-ink transition-colors group-hover:text-accent">
                {s.title}
              </span>
              <span className="ident hidden shrink-0 sm:inline">{s.topic}</span>
              <span className="shrink-0 self-center text-accent opacity-0 transition-all duration-200 group-hover:translate-x-0.5 group-hover:opacity-100">
                <Icon name="send" size={13} />
              </span>
            </button>
          </motion.li>
        ))}
      </motion.ul>

      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.7, delay: 1.05, ease }}
        className="ident mt-8 text-center"
      >
        Or pose your own question below · ⌘K for the index
      </motion.p>
    </div>
  );
}

const ROMAN = ['', 'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII'];
const roman = (n: number) => ROMAN[n] ?? String(n);

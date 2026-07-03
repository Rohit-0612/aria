import { motion } from 'framer-motion';
import { PROMPT_SEEDS } from '../lib/mockData';
import { Icon, type IconName } from './Icon';

/*
  Front matter — the journal's opening pages. Aims & Scope, the editorial
  process (the four-agent pipeline as a numbered method), and a table of
  contents of selected clinical queries to begin a consultation.
*/

const PROCESS: { id: IconName; label: string; note: string }[] = [
  { id: 'guardrail', label: 'Triage', note: 'Confirms the query is within clinical scope.' },
  { id: 'navigator', label: 'Retrieval', note: 'Searches DiPiro and reranks passages by relevance.' },
  { id: 'generator', label: 'Synthesis', note: 'Drafts a grounded answer from the evidence.' },
  { id: 'judge', label: 'Adjudication', note: 'Scores faithfulness and grades the evidence.' },
];

const ease = [0.22, 1, 0.36, 1] as const;

export function EmptyState({ onPick }: { onPick: (query: string) => void }) {
  return (
    <div className="pb-4">
      {/* Aims & Scope */}
      <motion.section
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease }}
        className="mx-auto max-w-2xl"
      >
        <div className="text-center">
          <span className="sec text-accent">Editorial · Aims &amp; Scope</span>
        </div>
        <p className="dropcap copy mt-4 font-prose text-[1.06rem] leading-[1.74] text-ink-soft" lang="en">
          ARIA answers clinical pharmacotherapy questions the way a journal publishes
          evidence: every recommendation is retrieved from <em>DiPiro&apos;s
          Pharmacotherapy</em>, reranked for relevance, synthesised, and then adjudicated by
          an independent Judge agent that grades the certainty of the evidence and scores
          the answer&apos;s faithfulness to its sources. You read not only the conclusion,
          but the method and the references behind it.
        </p>
      </motion.section>

      <div className="rule-hair mx-auto mt-9 max-w-4xl" />

      <div className="mx-auto mt-9 grid max-w-4xl grid-cols-1 gap-x-12 gap-y-10 md:grid-cols-2">
        {/* Editorial process */}
        <motion.section
          initial="hidden"
          animate="show"
          variants={{ show: { transition: { staggerChildren: 0.08, delayChildren: 0.2 } } }}
        >
          <h2 className="sec mb-4 text-ink">Editorial process</h2>
          <ol>
            {PROCESS.map((p, i) => (
              <motion.li
                key={p.id}
                variants={{ hidden: { opacity: 0, x: -8 }, show: { opacity: 1, x: 0, transition: { ease } } }}
                className="flex gap-3 border-t border-line py-3 first:border-t-0"
              >
                <span className="mt-0.5 font-mono text-[0.7rem] tabular-nums text-accent">
                  0{i + 1}
                </span>
                <span className="text-accent/90">
                  <Icon name={p.id} size={15} />
                </span>
                <span className="min-w-0">
                  <span className="block font-prose text-[0.95rem] font-medium text-ink">
                    {p.label}
                  </span>
                  <span className="mt-0.5 block font-prose text-[0.84rem] leading-snug text-ink-soft">
                    {p.note}
                  </span>
                </span>
              </motion.li>
            ))}
          </ol>
        </motion.section>

        {/* Table of contents */}
        <motion.section
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.35, ease }}
        >
          <h2 className="sec mb-4 text-ink">In this issue · selected queries</h2>
          <ul>
            {PROMPT_SEEDS.map((s, i) => (
              <li key={s.id} className="border-t border-line first:border-t-0">
                <button
                  type="button"
                  onClick={() => onPick(s.query)}
                  className="group flex w-full items-baseline gap-3 py-3 text-left"
                >
                  <span className="font-mono text-[0.7rem] tabular-nums text-ink-faint">
                    {roman(i + 1)}
                  </span>
                  <span className="flex-1">
                    <span className="block font-prose text-[0.96rem] font-medium leading-snug text-ink transition-colors group-hover:text-accent">
                      {s.title}
                    </span>
                    <span className="ident">{s.topic}</span>
                  </span>
                  <span className="translate-x-0 text-ink-faint opacity-0 transition-all group-hover:translate-x-0.5 group-hover:opacity-100">
                    <Icon name="send" size={13} />
                  </span>
                </button>
              </li>
            ))}
          </ul>
          <p className="ident mt-4">Or pose your own below · press ⌘K for the index.</p>
        </motion.section>
      </div>
    </div>
  );
}

const ROMAN = ['', 'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII'];
const roman = (n: number) => ROMAN[n] ?? String(n);

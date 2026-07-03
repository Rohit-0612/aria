import { motion } from 'framer-motion';
import type { AssistantMessage, Message, UserMessage } from '../lib/types';
import { CitationProvider } from './citationContext';
import { ReasoningTrace } from './ReasoningTrace';
import { EvidenceLevel } from './EvidenceLevel';
import { Prose } from './Prose';
import { References } from './References';
import { SafetyNotes } from './SafetyNotes';
import { CopyButton } from './CopyButton';
import { Icon } from './Icon';

/* A ledger turn typeset as one article: the query is the title, ARIA's
   grounded response is the article body, with a margin evidence box and a
   numbered References section. */

const ROMAN = [
  '',
  'I',
  'II',
  'III',
  'IV',
  'V',
  'VI',
  'VII',
  'VIII',
  'IX',
  'X',
  'XI',
  'XII',
];
const roman = (n: number) => ROMAN[n] ?? String(n);

const fmtDate = (ts: number) =>
  new Date(ts).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });

export function MessageTurn({
  message,
  articleNo,
}: {
  message: Message;
  articleNo?: number;
}) {
  return message.role === 'user' ? (
    <UserEntry message={message} articleNo={articleNo} />
  ) : (
    <AssistantEntry message={message} />
  );
}

function UserEntry({ message, articleNo }: { message: UserMessage; articleNo?: number }) {
  return (
    <motion.header
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
      className="mt-14 first:mt-0"
    >
      {articleNo && articleNo > 1 && <div className="rule-double mb-10 opacity-70" />}

      <div className="text-center">
        <span className="sec text-accent">
          Article {articleNo ? roman(articleNo) : ''} · Clinical Query
        </span>
      </div>

      <h2 className="mx-auto mt-4 max-w-3xl text-balance text-center font-display text-[1.7rem] font-medium leading-[1.18] tracking-tight2 text-ink sm:text-[2.05rem]">
        {message.content}
      </h2>

      <div className="mt-4 flex flex-wrap items-center justify-center gap-x-3 gap-y-1">
        <span className="ident">Received {fmtDate(message.createdAt)}</span>
        <span className="text-line-strong">·</span>
        <span className="ident">
          Manuscript ARIA-{message.id.slice(-4).toUpperCase()}
        </span>
        <span className="text-line-strong">·</span>
        <span className="ident">Retrieval-augmented · adjudicated</span>
      </div>

      <div className="rule-hair mt-5" />
    </motion.header>
  );
}

function AssistantEntry({ message }: { message: AssistantMessage }) {
  const reasoning = message.phase === 'reasoning';
  const streaming = message.phase === 'streaming';
  const complete = message.phase === 'complete';
  const metaReady = (streaming || complete) && message.confidence > 0;

  return (
    <CitationProvider citations={message.citations}>
      <div className="mt-7 grid grid-cols-1 gap-x-10 gap-y-6 lg:grid-cols-[minmax(0,1fr)_13rem]">
        {/* Article body */}
        <div className="min-w-0">
          {/* Methods box — the reasoning pipeline */}
          {message.agentSteps.length > 0 && (
            <figure className="mb-6 border border-line bg-surface/50">
              <figcaption className="flex items-center gap-2 border-b border-line px-3 py-1.5">
                <Icon name="navigator" size={12} className="text-ink-faint" />
                <span className="sec !text-[0.54rem]">Box 1 · Retrieval &amp; adjudication method</span>
              </figcaption>
              <div className="px-3 py-3">
                <ReasoningTrace steps={message.agentSteps} complete={complete} />
              </div>
            </figure>
          )}

          {(message.content || metaReady) && (
            <div className="mb-3 flex items-baseline gap-3">
              <h3 className="sec !tracking-[0.22em] text-ink">Findings &amp; Recommendation</h3>
              <span className="h-px flex-1 bg-line" />
            </div>
          )}

          {message.content && <Prose content={message.content} streaming={streaming} variant="paper" />}

          {reasoning && !message.content && <ThinkingShimmer />}

          {message.safety && message.safety.length > 0 && complete && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.2 }}
              className="mt-7"
            >
              <span className="sec mb-2 block">Clinical notes</span>
              <SafetyNotes notes={message.safety} />
            </motion.div>
          )}

          {complete && message.citations.length > 0 && (
            <References citations={message.citations} />
          )}

          {complete && message.content && (
            <div className="rule-hair mt-8 flex items-center gap-3 pt-3">
              <span className="ident max-w-md">
                † Decision-support synthesis. Not a substitute for clinical judgment or
                primary literature.
              </span>
              <span className="ml-auto">
                <CopyButton text={message.content} label="Copy article text" />
              </span>
            </div>
          )}
        </div>

        {/* Margin — evidence classification */}
        <aside className="lg:sticky lg:top-20 lg:self-start">
          {metaReady && (
            <EvidenceLevel tier={message.evidenceTier} confidence={message.confidence} />
          )}
        </aside>
      </div>
    </CitationProvider>
  );
}

function ThinkingShimmer() {
  return (
    <div className="space-y-2.5" aria-hidden>
      {[100, 94, 97, 72].map((w, i) => (
        <motion.div
          key={i}
          className="h-3 bg-line"
          style={{ width: `${w}%` }}
          animate={{ opacity: [0.35, 0.7, 0.35] }}
          transition={{ duration: 1.6, repeat: Infinity, delay: i * 0.12 }}
        />
      ))}
    </div>
  );
}

import { AnimatePresence, motion } from 'framer-motion';
import type { AssistantMessage, Message, UserMessage } from '../lib/types';
import { CitationProvider, useCitations } from './citationContext';
import { ThinkingStrip } from './ThinkingStrip';
import { SourceRail } from './SourceRail';
import { AnswerMeta } from './AnswerMeta';
import { AriaMark } from './AriaMark';
import { Prose } from './Prose';
import { cn } from '../lib/utils';
import { SafetyNotes } from './SafetyNotes';
import { ErrorNotice } from './ErrorNotice';

/*
  A turn in the consultation.

  The reader's question is an ink slip tucked to the right; ARIA answers
  in the open, left-aligned under its mark, the way a colleague writes back.
  Everything that used to be article furniture — the method box, the margin
  classification, the bibliography — now lives in the thin strip above the
  answer and the instrument row below it.
*/

const ease = [0.22, 1, 0.36, 1] as const;
const expo = [0.19, 1, 0.22, 1] as const;

const fmtTime = (ts: number) =>
  new Date(ts).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });

export function MessageTurn({ message, index = 0 }: { message: Message; index?: number }) {
  return message.role === 'user' ? (
    <UserTurn message={message} number={Math.floor(index / 2) + 1} />
  ) : (
    <AssistantTurn message={message} />
  );
}

/* The reader's question, printed in reverse on an ink slip and numbered like
   a query in the paper's correspondence column. */
function UserTurn({ message, number }: { message: UserMessage; number: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 22, rotate: 0.6 }}
      animate={{ opacity: 1, y: 0, rotate: 0 }}
      transition={{ duration: 0.8, ease: expo }}
      className="mt-9 flex justify-end first:mt-0 sm:mt-10"
    >
      <div className="flex max-w-[90%] flex-col items-end sm:max-w-[76%]">
        <span className="mb-1.5 flex items-baseline gap-2 pr-0.5">
          <span className="head text-[0.85rem] leading-none">Q. {String(number).padStart(2, '0')}</span>
          <span className="ident">{fmtTime(message.createdAt)}</span>
        </span>
        <div className="slab rounded-[2px] px-3.5 py-2.5 shadow-[3px_4px_0_hsl(var(--ink)/0.12)] sm:px-4 sm:py-3">
          <p className="whitespace-pre-wrap font-prose text-[0.98rem] leading-[1.55] sm:text-[1.02rem]">
            {message.content}
          </p>
        </div>
      </div>
    </motion.div>
  );
}

function AssistantTurn({ message }: { message: AssistantMessage }) {
  const streaming = message.phase === 'streaming';
  const failed = message.phase === 'failed';
  const complete = message.phase === 'complete';
  const live = !complete && !failed;

  return (
    <CitationProvider citations={message.citations}>
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease }}
        className="mt-6 flex gap-3 sm:gap-4"
      >
        {/* On a phone the gutter costs a fifth of the line length, so the
            mark moves inline into the byline instead. */}
        <div className="sticky top-1 hidden self-start pt-[2px] sm:block">
          <AriaMark live={live} size={28} />
        </div>

        <div className="min-w-0 flex-1 pb-1">
          <div className="mb-2 flex items-center gap-2">
            <span className="sm:hidden">
              <AriaMark live={live} size={21} />
            </span>
            <span className="head text-[0.95rem] leading-none">ARIA</span>
            <span
              className={cn(
                'ident truncate',
                failed ? 'text-oxblood/90' : 'text-ink-faint/70',
              )}
            >
              {/* "grounded reply" is a claim about provenance. It is only
                  earned by a turn that actually produced grounded content. */}
              {live
                ? 'consulting the evidence'
                : failed
                  ? 'no answer produced'
                  : message.refusal === 'self_harm'
                    ? 'here to help'
                    : message.refusal === 'harm_others'
                      ? 'declined'
                      : message.outOfScope
                        ? 'outside clinical scope'
                        : 'grounded reply'}
            </span>
          </div>

          {message.agentSteps.length > 0 && (
            <div className="mb-3.5">
              <ThinkingStrip steps={message.agentSteps} complete={complete || failed} />
            </div>
          )}

          {/* A failed turn renders the fault and nothing else — no Prose,
              no safety notes, no instrument row, no source rail. */}
          {failed && message.error ? (
            <ErrorNotice error={message.error} />
          ) : message.content ? (
            <Prose content={message.content} streaming={streaming} />
          ) : (
            streaming && <AnswerSkeleton />
          )}

          {complete && !failed && message.safety && message.safety.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.45, delay: 0.12, ease }}
              className="mt-4"
            >
              <SafetyNotes notes={message.safety} />
            </motion.div>
          )}

          {complete && !failed && message.content && (
            <>
              <AnswerMeta message={message} />
              <RailSlot message={message} />
            </>
          )}
        </div>
      </motion.div>
    </CitationProvider>
  );
}

/** The rail only mounts once the reader asks for it, so replies stay light. */
function RailSlot({ message }: { message: AssistantMessage }) {
  const { railOpen } = useCitations();
  return (
    <AnimatePresence initial={false}>
      {railOpen && (
        <motion.div
          key="rail"
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: 'auto', opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          transition={{ duration: 0.32, ease }}
          className="overflow-hidden"
        >
          <SourceRail citations={message.citations} />
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function AnswerSkeleton() {
  return (
    <div className="space-y-2.5 py-1" aria-hidden>
      {[100, 92, 96, 64].map((w, i) => (
        <motion.div
          key={i}
          className="h-3 rounded-[1px] bg-line"
          style={{ width: `${w}%` }}
          animate={{ opacity: [0.3, 0.65, 0.3] }}
          transition={{ duration: 1.5, repeat: Infinity, delay: i * 0.12 }}
        />
      ))}
    </div>
  );
}

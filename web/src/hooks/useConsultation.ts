import { useCallback, useRef, useState } from 'react';
import type { AssistantMessage, HistoryTurn, Message } from '../lib/types';
import { consult } from '../lib/client';
import { uid } from '../lib/utils';

/**
 * Owns the conversation transcript and drives the streaming pipeline.
 * Consumes the transport's event stream and incrementally builds the
 * active assistant message (reasoning → streaming → complete | failed).
 *
 * One invariant governs this hook: a turn's evidence tier and confidence
 * stay null until a `meta` event supplies real, Judge-derived values. They
 * are never seeded with plausible-looking defaults, because the UI renders
 * them as clinical certainty claims — a seeded 'moderate' is what stamped
 * "MODERATE CERTAINTY" onto provider error text.
 */
/** Exchanges sent back for follow-up resolution. The server keeps the same. */
const HISTORY_EXCHANGES = 2;
const HISTORY_CHARS = 1200;

/**
 * The recent conversation, as the backend needs it to understand a
 * follow-up. Only exchanges that produced a real answer are sent: a failed
 * turn has no content, and a refusal says nothing about what "it" means.
 * Citation markers are stripped — they mean nothing outside their turn.
 */
export function historyFrom(messages: Message[]): HistoryTurn[] {
  const pairs: HistoryTurn[][] = [];
  for (let i = 0; i + 1 < messages.length; i++) {
    const q = messages[i];
    const a = messages[i + 1];
    if (q.role !== 'user' || a.role !== 'assistant') continue;
    if (a.phase !== 'complete' || a.outOfScope || !a.content.trim()) continue;
    const answer = a.content.replace(/\[\[\d+(?:\s*,\s*\d+)*\]\]/g, '').trim();
    pairs.push([
      { role: 'user', content: q.content },
      { role: 'assistant', content: answer.slice(0, HISTORY_CHARS) },
    ]);
  }
  return pairs.slice(-HISTORY_EXCHANGES).flat();
}

export function useConsultation(reducedMotion: boolean) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [busy, setBusy] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const patchAssistant = useCallback((id: string, patch: Partial<AssistantMessage>) => {
    setMessages((prev) =>
      prev.map((m) => (m.id === id && m.role === 'assistant' ? { ...m, ...patch } : m)),
    );
  }, []);

  const ask = useCallback(
    async (query: string) => {
      const q = query.trim();
      if (!q || busy) return;

      abortRef.current?.abort();
      const ac = new AbortController();
      abortRef.current = ac;

      const userMsg: Message = {
        id: uid('u'),
        role: 'user',
        content: q,
        createdAt: Date.now(),
      };
      const assistantId = uid('a');
      const assistantMsg: AssistantMessage = {
        id: assistantId,
        role: 'assistant',
        content: '',
        // Null, not 'moderate' — nothing has been graded yet.
        evidenceTier: null,
        confidence: null,
        citations: [],
        agentSteps: [],
        createdAt: Date.now(),
        phase: 'reasoning',
      };

      const history = historyFrom(messages);
      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      setBusy(true);

      let buffer = '';
      let failed = false;
      let streamingStarted = false;
      try {
        for await (const ev of consult(q, {
          speed: reducedMotion ? 0 : 1,
          signal: ac.signal,
          history,
        })) {
          switch (ev.type) {
            case 'steps':
              patchAssistant(assistantId, { agentSteps: ev.steps });
              break;
            case 'sources':
              // Ungraded passages, early, so inline markers resolve while
              // the answer streams. `meta` later replaces them with the
              // same list; the tier and score still wait for the Judge.
              patchAssistant(assistantId, { citations: ev.citations });
              break;
            case 'meta':
              // Arrives after the prose: the Judge can only score a
              // finished answer. The gauge and the source rail render on a
              // completed turn, so nothing is shown ungraded in between.
              patchAssistant(assistantId, {
                evidenceTier: ev.evidenceTier,
                confidence: ev.confidence,
                citations: ev.citations,
                safety: ev.safety,
                outOfScope: ev.outOfScope ?? false,
              });
              break;
            case 'token':
              // The first fragment is what puts the turn into `streaming`.
              // It used to be the `meta` event, which arrived before the
              // prose only because the prose was replayed from a finished
              // answer. Now the answer streams as it is written and `meta`
              // comes last — keyed off `meta`, the caret never appeared.
              buffer += ev.chunk;
              patchAssistant(assistantId, {
                content: buffer,
                ...(streamingStarted ? {} : { phase: 'streaming' as const }),
              });
              streamingStarted = true;
              break;
            case 'error':
              // Terminal. Drop anything already streamed and strip every
              // credibility marker: an error is not a partial answer. This
              // matters more now that prose streams — a failure part-way
              // through leaves half an answer on screen, and it goes.
              failed = true;
              buffer = '';
              patchAssistant(assistantId, {
                phase: 'failed',
                content: '',
                evidenceTier: null,
                confidence: null,
                citations: [],
                safety: undefined,
                error: { stage: ev.stage, code: ev.code, message: ev.message },
              });
              break;
            case 'done':
              if (!failed) patchAssistant(assistantId, { phase: 'complete' });
              break;
          }
        }
      } catch (err) {
        if ((err as DOMException)?.name !== 'AbortError') {
          // A transport failure is a failure too. Previously this wrote a
          // sentence into `content` and marked the turn complete, which the
          // UI then decorated as a graded reply.
          patchAssistant(assistantId, {
            phase: 'failed',
            content: '',
            evidenceTier: null,
            confidence: null,
            citations: [],
            safety: undefined,
            error: {
              stage: 'transport',
              code: 'unreachable',
              message:
                'The consultation was interrupted before ARIA could respond. No clinical content was generated.',
            },
          });
        }
      } finally {
        if (abortRef.current === ac) {
          setBusy(false);
          abortRef.current = null;
        }
      }
    },
    [busy, messages, patchAssistant, reducedMotion],
  );

  const stop = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setBusy(false);
    setMessages((prev) =>
      prev.map((m) =>
        m.role === 'assistant' && m.phase !== 'complete' && m.phase !== 'failed'
          ? { ...m, phase: 'complete' }
          : m,
      ),
    );
  }, []);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setBusy(false);
    setMessages([]);
  }, []);

  return { messages, busy, ask, stop, reset };
}

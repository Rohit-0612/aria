import { useCallback, useRef, useState } from 'react';
import type { AssistantMessage, Message } from '../lib/types';
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

      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      setBusy(true);

      let buffer = '';
      let failed = false;
      let streamingStarted = false;
      try {
        for await (const ev of consult(q, {
          speed: reducedMotion ? 0 : 1,
          signal: ac.signal,
        })) {
          switch (ev.type) {
            case 'steps':
              patchAssistant(assistantId, { agentSteps: ev.steps });
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
    [busy, patchAssistant, reducedMotion],
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

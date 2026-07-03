import { useCallback, useRef, useState } from 'react';
import type { AssistantMessage, Message } from '../lib/types';
import { consult } from '../lib/client';
import { uid } from '../lib/utils';

/**
 * Owns the conversation transcript and drives the streaming pipeline.
 * Consumes the transport's event stream and incrementally builds the
 * active assistant message (reasoning → streaming → complete).
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
        evidenceTier: 'moderate',
        confidence: 0,
        citations: [],
        agentSteps: [],
        createdAt: Date.now(),
        phase: 'reasoning',
      };

      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      setBusy(true);

      let buffer = '';
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
              patchAssistant(assistantId, {
                evidenceTier: ev.evidenceTier,
                confidence: ev.confidence,
                citations: ev.citations,
                safety: ev.safety,
                phase: 'streaming',
              });
              break;
            case 'token':
              buffer += ev.chunk;
              patchAssistant(assistantId, { content: buffer });
              break;
            case 'done':
              patchAssistant(assistantId, { phase: 'complete' });
              break;
          }
        }
      } catch (err) {
        if ((err as DOMException)?.name !== 'AbortError') {
          patchAssistant(assistantId, {
            phase: 'complete',
            content:
              buffer ||
              'The consultation was interrupted before ARIA could respond. Please try again.',
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
        m.role === 'assistant' && m.phase !== 'complete' ? { ...m, phase: 'complete' } : m,
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

import { describe, expect, it } from 'vitest';
import type { AssistantMessage, Message } from '../lib/types';
import { historyFrom } from './useConsultation';

const user = (content: string): Message => ({
  id: `u-${content}`,
  role: 'user',
  content,
  createdAt: 0,
});

const reply = (content: string, patch: Partial<AssistantMessage> = {}): Message => ({
  id: `a-${content}`,
  role: 'assistant',
  content,
  evidenceTier: 'strong',
  confidence: 0.9,
  citations: [],
  agentSteps: [],
  createdAt: 0,
  phase: 'complete',
  ...patch,
});

describe('historyFrom', () => {
  it('sends answered exchanges without their citation markers', () => {
    const history = historyFrom([
      user('First-line for hypertension?'),
      reply('Thiazides [[1]][[2]] or ACEIs [[3]].'),
    ]);
    expect(history).toEqual([
      { role: 'user', content: 'First-line for hypertension?' },
      { role: 'assistant', content: 'Thiazides  or ACEIs .' },
    ]);
  });

  it('skips failed turns and refusals — they say nothing about what "it" means', () => {
    const history = historyFrom([
      user('Price of Bitcoin?'),
      reply('Outside my scope.', { outOfScope: true }),
      user('Warfarin monitoring?'),
      reply('', { phase: 'failed' }),
    ]);
    expect(history).toEqual([]);
  });

  it('keeps only the last two exchanges, clipped', () => {
    const msgs: Message[] = [];
    for (const q of ['a', 'b', 'c']) msgs.push(user(q), reply(`${q} answer `.repeat(400)));
    const history = historyFrom(msgs);
    expect(history.map((t) => t.content.slice(0, 1))).toEqual(['b', 'b', 'c', 'c']);
    expect(Math.max(...history.map((t) => t.content.length))).toBeLessThanOrEqual(1200);
  });

  it('ignores the turn still in flight', () => {
    expect(historyFrom([user('q'), reply('partial', { phase: 'streaming' })])).toEqual([]);
  });
});

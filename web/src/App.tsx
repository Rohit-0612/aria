import { useCallback, useEffect, useRef, useState } from 'react';
import { Masthead } from './components/Masthead';
import { Nameplate } from './components/Nameplate';
import { EmptyState } from './components/EmptyState';
import { MessageTurn } from './components/MessageTurn';
import { Composer } from './components/Composer';
import { CommandPalette } from './components/CommandPalette';
import { useTheme } from './hooks/useTheme';
import { useReducedMotion } from './hooks/useReducedMotion';
import { useConsultation } from './hooks/useConsultation';
import BorderGlow from './components/BorderGlow';

export default function App() {
  const { theme, toggle } = useTheme();
  const reduced = useReducedMotion();
  const { messages, busy, ask, stop, reset } = useConsultation(reduced);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const anchorRef = useRef<HTMLDivElement>(null);
  const lastCount = useRef(0);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setPaletteOpen((v) => !v);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  useEffect(() => {
    if (messages.length > lastCount.current) {
      anchorRef.current?.scrollIntoView({
        behavior: reduced ? 'auto' : 'smooth',
        block: 'end',
      });
    }
    lastCount.current = messages.length;
  }, [messages.length, reduced]);

  const send = useCallback(
    (q: string) => {
      setPaletteOpen(false);
      ask(q);
    },
    [ask],
  );

  const hasConversation = messages.length > 0;

  // Count the assistant articles to number them (Article I, II, …).
  let articleNo = 0;

  return (
    <div className="flex min-h-dvh flex-col">
      <Masthead
        theme={theme}
        onToggleTheme={toggle}
        onReset={reset}
        hasConversation={hasConversation}
        busy={busy}
      />

      <main className="relative flex-1 px-3 pb-2 pt-5 sm:px-6 sm:pt-8">
        <BorderGlow
          backgroundColor="hsl(var(--page))"
          borderRadius={12}
          glowRadius={60}
          glowIntensity={0.7}
          edgeSensitivity={25}
          animated={!reduced}
          glowColor={theme === 'dark' ? '34 80 62' : '26 68 45'}
          colors={
            theme === 'dark'
              ? ['#fbbf24', '#ef4444', '#2dd4bf']
              : ['#d97706', '#991b1b', '#0f766e']
          }
          className="mx-auto max-w-[62rem]"
        >
          <article className="relative px-6 pb-16 pt-8 sm:px-12 sm:pt-12 lg:px-16">
            <Nameplate />

            {!hasConversation ? (
              <EmptyState onPick={send} />
            ) : (
              <div>
                {messages.map((m) => {
                  if (m.role === 'user') articleNo += 1;
                  return (
                    <MessageTurn
                      key={m.id}
                      message={m}
                      articleNo={m.role === 'user' ? articleNo : undefined}
                    />
                  );
                })}
                <div ref={anchorRef} className="h-1" />
              </div>
            )}

            <footer className="rule-hair mt-12 flex items-center justify-between pt-3">
              <span className="ident">ARIA · Vol. 1 (4) · 2026</span>
              <span className="ident">Grounded in DiPiro&apos;s Pharmacotherapy, 12e</span>
            </footer>
          </article>
        </BorderGlow>
      </main>

      <Composer onSend={send} onStop={stop} busy={busy} onOpenPalette={() => setPaletteOpen(true)} />

      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        onSend={send}
        onReset={() => {
          setPaletteOpen(false);
          reset();
        }}
        onToggleTheme={toggle}
      />
    </div>
  );
}

import { useCallback, useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { Masthead } from './components/Masthead';
import { TitlePage } from './components/TitlePage';
import { EmptyState } from './components/EmptyState';
import { MessageTurn } from './components/MessageTurn';
import { Composer } from './components/Composer';
import { CommandPalette } from './components/CommandPalette';
import { Icon } from './components/Icon';
import { useTheme } from './hooks/useTheme';
import { useReducedMotion } from './hooks/useReducedMotion';
import { useConsultation } from './hooks/useConsultation';
import { useAppHeight } from './hooks/useViewport';
import BorderGlow from './components/BorderGlow';

/*
  The consultation surface.

  One framed sheet holds the whole exchange: the transcript scrolls inside
  it and the composer stays docked at its foot, so the app reads as a room
  you're talking in rather than a document that keeps reprinting itself.
*/

export default function App() {
  const { theme, toggle } = useTheme();
  const reduced = useReducedMotion();
  useAppHeight();
  const { messages, busy, ask, stop, reset } = useConsultation(reduced);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [covered, setCovered] = useState(true);
  const uncover = useCallback(() => setCovered(false), []);

  const scrollRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const lastCount = useRef(0);
  /* Whether the transcript keeps following new text. Held in a ref because our
     own scrolling emits scroll events too, and reading a stale state value
     mid-animation used to strand the follow half-way through an answer.
     We only ever scroll *down*, so an upward move is the reader's doing — that
     is the signal that detaches, and reaching the end re-attaches. */
  const stick = useRef(true);
  const lastTop = useRef(0);
  const [atEnd, setAtEnd] = useState(true);

  const measure = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return true;
    const end = el.scrollHeight - el.scrollTop - el.clientHeight < 90;
    setAtEnd(end);
    return end;
  }, []);

  const scrollToEnd = useCallback(
    (smooth: boolean) => {
      const el = scrollRef.current;
      if (!el) return;
      el.scrollTo({ top: el.scrollHeight, behavior: smooth && !reduced ? 'smooth' : 'auto' });
      // A scroll that lands where it already was fires no event, so the pill
      // would otherwise keep a stale reading.
      requestAnimationFrame(measure);
    },
    [reduced, measure],
  );

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

  /* A new turn re-attaches the transcript and glides to it: you always want to
     see your own question land. */
  useEffect(() => {
    const newTurn = messages.length > lastCount.current;
    lastCount.current = messages.length;
    // Nothing to follow yet: on a short screen this would otherwise open the
    // empty state already scrolled past its own nameplate.
    if (!messages.length || !newTurn) return;
    stick.current = true;
    scrollToEnd(true);
  }, [messages, scrollToEnd]);

  /* Everything that *grows* the transcript — streamed tokens, the meta row
     landing, a source passage opening — is followed here. Watching the content
     box rather than reacting to scroll events matters: a scroll event can be
     delivered after the next growth, reporting a gap that is already wrong. */
  useEffect(() => {
    const content = contentRef.current;
    if (!content) return;
    const ro = new ResizeObserver(() => {
      if (stick.current) scrollToEnd(false);
      else measure();
    });
    ro.observe(content);
    return () => ro.disconnect();
  }, [scrollToEnd, measure]);

  const onScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const end = measure();
    if (el.scrollTop < lastTop.current - 1) stick.current = false; // reader pulled up
    if (end) stick.current = true; // back at the end: follow again
    lastTop.current = el.scrollTop;
  }, [measure]);

  const toLatest = useCallback(() => {
    stick.current = true;
    scrollToEnd(true);
  }, [scrollToEnd]);

  const send = useCallback(
    (q: string) => {
      setPaletteOpen(false);
      ask(q);
    },
    [ask],
  );

  const hasConversation = messages.length > 0;

  return (
    /* Pinned to the visual viewport: on iOS the keyboard shrinks it, and the
       composer has to ride up with it rather than hide underneath. */
    <div
      className="fixed inset-x-0 top-0 flex flex-col overflow-hidden"
      style={{ height: 'var(--app-h, 100dvh)' }}
    >
      <AnimatePresence>
        {covered && <TitlePage reduced={reduced} onDone={uncover} />}
      </AnimatePresence>

      <Masthead
        theme={theme}
        onToggleTheme={toggle}
        onReset={reset}
        hasConversation={hasConversation}
        busy={busy}
      />

      <main className="pb-safe relative min-h-0 flex-1 px-1.5 pt-2 sm:px-6 sm:pt-5">
        {/* The surface rises to meet the reader as the cover lifts away. */}
        <motion.div
          initial={false}
          animate={covered ? { opacity: 0, y: 22 } : { opacity: 1, y: 0 }}
          transition={{ duration: reduced ? 0 : 0.75, ease: [0.22, 1, 0.36, 1] }}
          className="mx-auto h-full w-full max-w-[56rem]"
        >
          <BorderGlow
            backgroundColor="hsl(var(--page))"
            borderRadius={16}
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
            className="h-full"
          >
            <div className="flex min-h-0 flex-1 flex-col">
              {/* Transcript — its own positioning context, so the overlays
                  below sit above the transcript and never over the composer. */}
              <div className="relative min-h-0 flex-1">
                <div
                  ref={scrollRef}
                  onScroll={onScroll}
                  data-transcript
                  className="h-full overflow-y-auto overscroll-contain"
                >
                  <div
                    ref={contentRef}
                    className="mx-auto flex min-h-full w-full max-w-3xl flex-col px-3.5 pb-6 pt-4 sm:px-8 sm:pb-8 sm:pt-5"
                  >
                    <AnimatePresence mode="wait">
                      {!hasConversation ? (
                        <EmptyState key="empty" onPick={send} />
                      ) : (
                        <div key="thread">
                          {messages.map((m) => (
                            <MessageTurn key={m.id} message={m} />
                          ))}
                        </div>
                      )}
                    </AnimatePresence>
                  </div>
                </div>

                {/* The transcript slips under the top edge rather than butting into it. */}
                <div
                  aria-hidden
                  className="pointer-events-none absolute inset-x-0 top-0 h-6 bg-gradient-to-b from-page to-transparent"
                />

                <AnimatePresence>
                  {!atEnd && hasConversation && (
                    <motion.button
                      type="button"
                      onClick={toLatest}
                      /* The centering shift lives in the animation, not a
                         class — framer owns `transform` on this element. */
                      initial={{ opacity: 0, y: 8, scale: 0.95, x: '-50%' }}
                      animate={{ opacity: 1, y: 0, scale: 1, x: '-50%' }}
                      exit={{ opacity: 0, y: 8, scale: 0.95, x: '-50%' }}
                      transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
                      className="absolute bottom-3 left-1/2 z-10 inline-flex items-center gap-1.5 rounded-full border border-line-strong bg-surface-raised px-3 py-2 font-mono text-[0.58rem] uppercase tracking-[0.12em] text-ink-soft shadow-peek transition-colors hover:border-accent/60 hover:text-ink sm:py-1.5"
                    >
                      <span className="rotate-90">
                        <Icon name="chevron" size={11} />
                      </span>
                      Latest
                    </motion.button>
                  )}
                </AnimatePresence>
              </div>

              <Composer
                onSend={send}
                onStop={stop}
                busy={busy}
                onOpenPalette={() => setPaletteOpen(true)}
                autoFocusKey={covered ? undefined : `${messages.length}-${busy}`}
              />
            </div>
          </BorderGlow>
        </motion.div>
      </main>

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

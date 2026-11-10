import { useCallback, useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { Masthead } from './components/Masthead';
import { CapsuleCover } from './components/CapsuleCover';
import { Curtain } from './components/Curtain';
import { Cursor } from './components/Cursor';
import { EmptyState } from './components/EmptyState';
import { MessageTurn } from './components/MessageTurn';
import { Composer } from './components/Composer';
import { CommandPalette } from './components/CommandPalette';
import { Icon } from './components/Icon';
import { useTheme } from './hooks/useTheme';
import { useReducedMotion } from './hooks/useReducedMotion';
import { useConsultation } from './hooks/useConsultation';
import { useAppHeight } from './hooks/useViewport';
import { curtain, tokenRGB } from './lib/curtain';

/*
  The consultation surface.

  One printed sheet holds the whole exchange: the transcript scrolls inside
  it and the composer stays docked at its foot, so the app reads as a room
  you're talking in rather than a document that keeps reprinting itself.

  The app opens from the capsule cover (CapsuleCover). After that, page turns
  go through the paper curtain (lib/curtain.ts): a new consultation is a fresh
  sheet torn across the old one, and the Day / Night editions swap under a
  sheet of the other ink.
*/

export default function App() {
  const { theme, toggle } = useTheme();
  const reduced = useReducedMotion();
  useAppHeight();
  const { messages, busy, ask, stop, reset } = useConsultation(reduced);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [covered, setCovered] = useState(true);
  /* The front page plays its entrance once the curtain starts to lift. */
  const [play, setPlay] = useState(false);

  // The capsule cracks open: the front page plays in as its halves part.
  const opening = useCallback(() => {
    setTimeout(() => setPlay(true), reduced ? 0 : 250);
  }, [reduced]);
  const uncover = useCallback(() => setCovered(false), []);

  /* A fresh consultation is a fresh sheet, torn across the old one. */
  const newConsult = useCallback(() => {
    setPaletteOpen(false);
    curtain.turn({
      color: () => tokenRGB('--ink'),
      label: 'New consult',
      // The fresh front page waits under the sheet, then plays as it tears.
      during: () => {
        setPlay(false);
        reset();
      },
      onReveal: () => setTimeout(() => setPlay(true), reduced ? 0 : 200),
    });
  }, [reset, reduced]);

  /* The other edition: a sheet in this edition's ink is, near enough, the
     other edition's paper — tear it across, swap, tear it away. */
  const switchEdition = useCallback(() => {
    setPaletteOpen(false);
    curtain.turn({
      color: () => tokenRGB('--ink'),
      label: theme === 'dark' ? 'Day edition' : 'Night edition',
      during: toggle,
    });
  }, [theme, toggle]);

  const scrollRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const lastCount = useRef(0);
  /* Whether the transcript keeps following new text. Held in a ref because our
     own scrolling emits scroll events too, and reading a stale state value
     mid-animation used to strand the follow half-way through an answer.
     We only ever scroll *down*, so an upward move is the reader's doing — that
     is the signal that detaches, and reaching the end re-attaches. */
  const stick = useRef(true);
  /* Only a conversation is followed: the front page is read from the top,
     even when it is taller than a phone's screen. */
  const following = useRef(false);
  following.current = messages.length > 0;
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
      if (stick.current && following.current) scrollToEnd(false);
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
      {covered && <CapsuleCover reduced={reduced} onOpen={opening} onDone={uncover} />}

      <Masthead
        theme={theme}
        onToggleTheme={switchEdition}
        onReset={newConsult}
        onOpenPalette={() => setPaletteOpen(true)}
        hasConversation={hasConversation}
        busy={busy}
      />

      <main className="pb-safe relative min-h-0 flex-1 px-2 pt-3 sm:px-6 sm:pt-6">
        <motion.div
          initial={false}
          animate={play ? { y: 0 } : { y: 18 }}
          transition={{ duration: reduced ? 0 : 1.2, ease: [0.19, 1, 0.22, 1] }}
          className="relative mx-auto h-full w-full max-w-[58rem]"
        >
          {/* The sheet beneath the sheet — a stack of newsprint on the desk. */}
          <div
            aria-hidden
            className="absolute inset-0 translate-x-[3px] translate-y-[5px] rotate-[0.45deg] border border-rule/30 bg-surface"
          />
          <div className="relative flex h-full flex-col overflow-hidden border border-rule bg-page shadow-[0_28px_60px_-34px_hsl(var(--shadow)/0.55)]">
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
                  className="mx-auto flex min-h-full w-full max-w-3xl flex-col px-3.5 pb-6 pt-4 sm:px-8 sm:pb-8 sm:pt-6"
                >
                  <AnimatePresence mode="wait">
                    {!hasConversation ? (
                      <EmptyState key="empty" onPick={send} play={play} reduced={reduced} />
                    ) : (
                      <div key="thread">
                        {messages.map((m, i) => (
                          <MessageTurn key={m.id} message={m} index={i} />
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
                    className="slab absolute bottom-3 left-1/2 z-10 inline-flex items-center gap-1.5 px-3 py-2 font-display text-[0.85rem] font-bold uppercase leading-none tracking-[-0.02em] shadow-peek transition-colors hover:bg-accent sm:py-1.5"
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
        </motion.div>
      </main>

      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        onSend={send}
        onReset={newConsult}
        onToggleTheme={switchEdition}
      />

      <Curtain />
      <Cursor />
      <div aria-hidden className="paper-grain" />
    </div>
  );
}

import { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { Icon } from './Icon';
import { useIsDesktop } from '../hooks/useViewport';
import { cn } from '../lib/utils';

/*
  The composer — docked at the foot of the consultation surface.

  A single field that grows with the question, framed by a hairline that
  warms to the accent on focus. Enter submits, Shift+Enter breaks the line.
  While ARIA is working the send control morphs into a stop, and a thin
  filament crawls the top edge of the field so the wait has a heartbeat.
*/

interface Props {
  onSend: (text: string) => void;
  onStop: () => void;
  busy: boolean;
  onOpenPalette: () => void;
  /** Focus the field when the surface is revealed and after each reply. */
  autoFocusKey?: string | number;
}

const ease = [0.22, 1, 0.36, 1] as const;

export function Composer({ onSend, onStop, busy, onOpenPalette, autoFocusKey }: Props) {
  const [value, setValue] = useState('');
  const taRef = useRef<HTMLTextAreaElement>(null);
  const desktop = useIsDesktop();

  useEffect(() => {
    const ta = taRef.current;
    if (!ta) return;
    ta.style.height = '0px';
    ta.style.height = Math.min(ta.scrollHeight, desktop ? 190 : 120) + 'px';
  }, [value, desktop]);

  useEffect(() => {
    // Never steal focus on a phone — it would throw the keyboard up over
    // the answer the reader is trying to read.
    if (autoFocusKey === undefined || busy || !desktop) return;
    taRef.current?.focus();
  }, [autoFocusKey, busy, desktop]);

  const submit = () => {
    const v = value.trim();
    if (!v || busy) return;
    onSend(v);
    setValue('');
  };

  const ready = value.trim().length > 0;

  return (
    <div className="relative shrink-0 border-t border-line/70 bg-page/80 px-2.5 pb-2.5 pt-2.5 backdrop-blur-sm sm:px-5 sm:pb-4 sm:pt-3">
      <div className="mx-auto w-full max-w-3xl">
        <div
          className={cn(
            'group relative overflow-hidden rounded-[14px] border bg-surface-raised transition-all duration-300',
            'border-line focus-within:border-accent/55',
            'focus-within:shadow-[0_0_0_3px_hsl(var(--accent)/0.12),0_10px_30px_-24px_hsl(var(--shadow)/0.7)]',
          )}
        >
          {/* Working filament along the top edge. */}
          <AnimatePresence>
            {busy && (
              <motion.span
                aria-hidden
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="absolute inset-x-0 top-0 h-px overflow-hidden"
              >
                <motion.span
                  className="block h-px w-1/3 bg-gradient-to-r from-transparent via-accent to-transparent"
                  animate={{ x: ['-100%', '300%'] }}
                  transition={{ duration: 1.8, repeat: Infinity, ease: 'easeInOut' }}
                />
              </motion.span>
            )}
          </AnimatePresence>

          <div className="flex items-end gap-2 px-2.5 py-2 sm:px-3 sm:py-2.5">
            <span className="pointer-events-none mb-[11px] hidden select-none font-mono text-[0.72rem] text-accent/60 transition-colors group-focus-within:text-accent sm:mb-[9px] sm:block">
              §
            </span>

            <label htmlFor="aria-composer" className="sr-only">
              Ask ARIA a clinical pharmacotherapy question
            </label>
            <textarea
              id="aria-composer"
              ref={taRef}
              value={value}
              rows={1}
              /* A phone can't fit the long invitation without eating a third
                 of the screen before a word is typed. */
              placeholder={
                desktop
                  ? 'Ask about dosing, interactions, monitoring, or the evidence behind a therapy…'
                  : 'Ask a clinical question…'
              }
              onChange={(e) => setValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  submit();
                }
              }}
              /* 16px minimum — anything smaller makes iOS zoom the page on focus. */
              className="max-h-[120px] flex-1 resize-none bg-transparent px-1 py-2 font-prose text-[1rem] leading-relaxed text-ink placeholder:text-ink-faint/75 focus:outline-none sm:max-h-[190px] sm:px-0 sm:py-1.5"
            />

            <div className="mb-px grid h-10 w-10 shrink-0 place-items-center sm:h-9 sm:w-9">
              <AnimatePresence mode="wait" initial={false}>
                {busy ? (
                  <motion.button
                    key="stop"
                    type="button"
                    onClick={onStop}
                    aria-label="Stop generating"
                    initial={{ scale: 0.7, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    exit={{ scale: 0.7, opacity: 0 }}
                    transition={{ duration: 0.18, ease }}
                    whileTap={{ scale: 0.9 }}
                    className="grid h-10 w-10 place-items-center rounded-full border border-line-strong sm:h-9 sm:w-9 text-ink-soft transition-colors hover:border-oxblood hover:text-oxblood"
                  >
                    <Icon name="stop" size={13} />
                  </motion.button>
                ) : (
                  <motion.button
                    key="send"
                    type="button"
                    onClick={submit}
                    disabled={!ready}
                    aria-label="Send question"
                    initial={{ scale: 0.7, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    exit={{ scale: 0.7, opacity: 0 }}
                    transition={{ duration: 0.18, ease }}
                    whileTap={{ scale: 0.9 }}
                    className={cn(
                      'grid h-10 w-10 place-items-center rounded-full transition-all duration-300 sm:h-9 sm:w-9',
                      ready
                        ? 'bg-accent text-page shadow-[0_4px_14px_-6px_hsl(var(--accent)/0.9)] hover:brightness-105'
                        : 'border border-line text-ink-faint/70',
                    )}
                  >
                    <Icon name="send" size={15} strokeWidth={2} />
                  </motion.button>
                )}
              </AnimatePresence>
            </div>
          </div>
        </div>

        <div className="mt-1.5 flex items-center justify-between gap-3 px-1 sm:mt-2">
          <button
            type="button"
            onClick={onOpenPalette}
            className="-my-1 inline-flex shrink-0 items-center gap-1.5 py-1 font-mono text-[0.56rem] uppercase tracking-[0.1em] text-ink-faint transition-colors hover:text-ink-soft"
          >
            <kbd className="hidden rounded-[4px] border border-line bg-surface px-1.5 py-0.5 text-[0.54rem] normal-case sm:inline">
              ⌘K
            </kbd>
            <Icon name="book" size={11} className="sm:hidden" />
            saved consults
          </button>
          {/* The full disclaimer needs room; a phone gets the short form. */}
          <span className="truncate font-mono text-[0.54rem] text-ink-faint/80">
            <span className="hidden sm:inline">
              Decision support · not a substitute for clinical judgment
            </span>
            <span className="sm:hidden">Decision support only</span>
          </span>
        </div>
      </div>
    </div>
  );
}

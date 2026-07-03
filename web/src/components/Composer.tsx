import { useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { Icon } from './Icon';
import { cn } from '../lib/utils';

/*
  The composer — set as a manuscript submission slip. A growing field framed
  like a form on journal stock. Enter submits, Shift+Enter newlines; while
  ARIA adjudicates, the submit control becomes a stop.
*/

interface Props {
  onSend: (text: string) => void;
  onStop: () => void;
  busy: boolean;
  onOpenPalette: () => void;
}

export function Composer({ onSend, onStop, busy, onOpenPalette }: Props) {
  const [value, setValue] = useState('');
  const taRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const ta = taRef.current;
    if (!ta) return;
    ta.style.height = '0px';
    ta.style.height = Math.min(ta.scrollHeight, 200) + 'px';
  }, [value]);

  const submit = () => {
    const v = value.trim();
    if (!v || busy) return;
    onSend(v);
    setValue('');
  };

  return (
    <div className="pointer-events-none sticky bottom-0 z-20">
      <div className="h-8 bg-gradient-to-t from-desk to-transparent" />
      <div className="bg-desk pb-4">
        <div className="pointer-events-auto mx-auto max-w-2xl px-4 sm:px-6">
          <div className="mb-1.5 flex items-center gap-2 px-0.5">
            <span className="sec !text-[0.54rem]">Submit a clinical query</span>
            <span className="h-px flex-1 bg-rule/25" />
          </div>
          <div
            className={cn(
              'sheet group relative flex items-end gap-2 px-3 py-2.5 transition-shadow',
              'focus-within:ring-1 focus-within:ring-accent',
            )}
          >
            <span className="pointer-events-none mb-[7px] select-none font-mono text-[0.7rem] text-accent/70">
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
              placeholder="On dosing, interactions, monitoring, or the evidence behind a therapy…"
              onChange={(e) => setValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  submit();
                }
              }}
              className="max-h-[200px] flex-1 resize-none bg-transparent py-1 font-prose text-[1rem] leading-relaxed text-ink placeholder:text-ink-faint/80 focus:outline-none"
            />

            {busy ? (
              <button
                type="button"
                onClick={onStop}
                aria-label="Stop generating"
                className="mb-px grid h-9 w-9 place-items-center border border-line-strong text-ink-soft transition-colors hover:border-oxblood hover:text-oxblood"
              >
                <Icon name="stop" size={15} />
              </button>
            ) : (
              <motion.button
                type="button"
                onClick={submit}
                disabled={!value.trim()}
                aria-label="Submit query"
                whileTap={{ scale: 0.92 }}
                className={cn(
                  'mb-px grid h-9 w-9 place-items-center transition-colors',
                  value.trim()
                    ? 'bg-accent text-page hover:brightness-105'
                    : 'border border-line text-ink-faint',
                )}
              >
                <Icon name="send" size={16} strokeWidth={1.9} />
              </motion.button>
            )}
          </div>

          <div className="mt-2 flex items-center justify-between px-1">
            <button
              type="button"
              onClick={onOpenPalette}
              className="inline-flex items-center gap-1.5 font-mono text-[0.58rem] text-ink-faint transition-colors hover:text-ink-soft"
            >
              <kbd className="border border-line bg-surface px-1.5 py-0.5 text-[0.56rem]">⌘K</kbd>
              index of queries
            </button>
            <span className="font-mono text-[0.56rem] text-ink-faint">
              Enter to submit · Shift+Enter for a new line
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

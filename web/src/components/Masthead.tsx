import { motion } from 'framer-motion';
import { Icon } from './Icon';
import { Roll } from './fx';
import { cn } from '../lib/utils';

/*
  The masthead — ARIA's running head across the top of the desk. The mark on
  the left, the nameplate in the middle, the reading controls on the right,
  and a hairline-over-hairline rule beneath, like the foot of a newspaper's
  front-page banner. Labels roll over to a fresh copy on hover.
*/

interface Props {
  theme: 'light' | 'dark';
  onToggleTheme: () => void;
  onReset: () => void;
  onOpenPalette: () => void;
  hasConversation: boolean;
  busy: boolean;
}

const control =
  'inline-flex h-8 items-center gap-1.5 font-display text-[1.02rem] font-bold uppercase leading-none tracking-[-0.02em] text-ink transition-colors hover:text-accent sm:h-7';

export function Masthead({ theme, onToggleTheme, onReset, onOpenPalette, hasConversation, busy }: Props) {
  return (
    <header className="pt-safe rule-press relative z-30 shrink-0 bg-desk">
      <div className="mx-auto grid max-w-[64rem] grid-cols-[1fr_auto] items-center gap-3 px-3 py-2 sm:px-6 md:grid-cols-[1fr_auto_1fr]">
        <div className="flex items-center gap-2.5">
          <span className="head text-[1.35rem] leading-none">
            ARIA<sup className="ml-px font-prose text-[0.55em] font-normal normal-case">©</sup>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="relative flex h-1.5 w-1.5">
              {busy && (
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent/60" />
              )}
              <span
                className={cn(
                  'relative inline-flex h-1.5 w-1.5 rounded-full',
                  busy ? 'bg-accent' : 'bg-tier-strong',
                )}
              />
            </span>
            <span className="hidden font-mono text-[0.55rem] uppercase tracking-[0.14em] text-ink-faint sm:inline">
              {busy ? 'Going to press' : 'Ready'}
            </span>
          </span>
        </div>

        <span className="hidden whitespace-nowrap font-display text-[1.6rem] font-semibold leading-none tracking-[-0.01em] md:block">
          The Consultation Ledger
        </span>

        <nav className="flex items-center justify-end gap-3.5 sm:gap-5" aria-label="Consultation">
          {hasConversation && (
            <motion.button
              type="button"
              onClick={onReset}
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              className={control}
            >
              <Icon name="plus" size={13} className="sm:hidden" />
              <span className="hidden sm:inline">
                <Roll>New consult</Roll>
              </span>
              <span className="sr-only sm:hidden">New consult</span>
            </motion.button>
          )}

          <button type="button" onClick={onOpenPalette} className={cn(control, 'hidden sm:inline-flex')}>
            <Roll>Saved</Roll>
            <kbd className="rounded-[2px] border border-rule/40 px-1 py-0.5 font-mono text-[0.52rem] font-normal normal-case tracking-normal text-ink-faint">
              ⌘K
            </kbd>
          </button>

          <button
            type="button"
            onClick={onToggleTheme}
            aria-label={`Switch to the ${theme === 'dark' ? 'Day' : 'Night'} edition`}
            className={control}
          >
            <Icon name={theme === 'dark' ? 'sun' : 'moon'} size={13} />
            <span className="hidden sm:inline">
              <Roll>{theme === 'dark' ? 'Day' : 'Night'}</Roll>
            </span>
          </button>
        </nav>
      </div>
    </header>
  );
}

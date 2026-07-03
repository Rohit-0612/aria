import { motion } from 'framer-motion';
import { Icon } from './Icon';
import { cn } from '../lib/utils';

/*
  Running head — the persistent page header of the journal. Slim, set in
  small caps, with the volume/issue line and the reading controls.
*/

interface Props {
  theme: 'light' | 'dark';
  onToggleTheme: () => void;
  onReset: () => void;
  hasConversation: boolean;
  busy: boolean;
}

export function Masthead({ theme, onToggleTheme, onReset, hasConversation, busy }: Props) {
  return (
    <header className="sticky top-0 z-30 border-b border-rule/30 bg-desk/85 backdrop-blur-md">
      <div className="mx-auto flex max-w-[62rem] items-center gap-4 px-4 py-2.5 sm:px-6">
        <div className="flex items-center gap-2 text-ink">
          <Icon name="aria" size={17} className="text-accent" />
          <span className="font-display text-[0.95rem] font-semibold tracking-tight2">ARIA</span>
          <span className="hidden font-mono text-[0.56rem] uppercase tracking-[0.18em] text-ink-faint sm:inline">
            Clinical Pharmacotherapy
          </span>
        </div>

        <span className="ml-auto hidden font-mono text-[0.56rem] uppercase tracking-[0.16em] text-ink-faint md:inline">
          Vol. 1 (4) · 2026
        </span>

        <div className="ml-auto flex items-center gap-1.5 md:ml-4">
          <span className="mr-1 hidden items-center gap-1.5 sm:flex">
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
            <span className="font-mono text-[0.55rem] uppercase tracking-[0.14em] text-ink-faint">
              {busy ? 'In review' : 'Ready'}
            </span>
          </span>

          {hasConversation && (
            <motion.button
              type="button"
              onClick={onReset}
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              className="inline-flex items-center gap-1.5 border border-line px-2 py-1 font-mono text-[0.56rem] uppercase tracking-[0.12em] text-ink-soft transition-colors hover:border-line-strong hover:text-ink"
            >
              <Icon name="plus" size={12} />
              <span className="hidden sm:inline">New issue</span>
            </motion.button>
          )}

          <button
            type="button"
            onClick={onToggleTheme}
            aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
            className="grid h-7 w-7 place-items-center border border-line text-ink-soft transition-colors hover:border-line-strong hover:text-ink"
          >
            <motion.span
              key={theme}
              initial={{ rotate: -30, opacity: 0 }}
              animate={{ rotate: 0, opacity: 1 }}
              transition={{ duration: 0.3 }}
            >
              <Icon name={theme === 'dark' ? 'sun' : 'moon'} size={14} />
            </motion.span>
          </button>
        </div>
      </div>
    </header>
  );
}

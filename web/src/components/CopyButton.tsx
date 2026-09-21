import { useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { Icon } from './Icon';
import { cn } from '../lib/utils';

/** Copy plain text with a quiet check-mark confirmation. */
export function CopyButton({ text, label = 'Copy answer' }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false);

  const onCopy = async () => {
    try {
      // Strip our [[n]] markers from the copied text.
      await navigator.clipboard.writeText(text.replace(/\[\[(\d+)\]\]/g, ''));
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      /* clipboard unavailable */
    }
  };

  return (
    <button
      type="button"
      onClick={onCopy}
      aria-label={label}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-[3px] px-2 py-1 font-mono text-[0.6rem] uppercase tracking-[0.1em] text-ink-faint transition-colors hover:bg-line/50 hover:text-ink-soft',
      )}
    >
      <span className="relative grid h-3.5 w-3.5 place-items-center">
        <AnimatePresence mode="wait" initial={false}>
          {copied ? (
            <motion.span
              key="check"
              initial={{ scale: 0, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0, opacity: 0 }}
              className="absolute text-tier-strong"
            >
              <Icon name="check" size={14} strokeWidth={2.2} />
            </motion.span>
          ) : (
            <motion.span
              key="copy"
              initial={{ scale: 0, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0, opacity: 0 }}
              className="absolute"
            >
              <Icon name="copy" size={14} />
            </motion.span>
          )}
        </AnimatePresence>
      </span>
      {copied ? 'Copied' : 'Copy'}
    </button>
  );
}

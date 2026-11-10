import { useEffect, useMemo, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { PROMPT_SEEDS } from '../lib/mockData';
import { cn } from '../lib/utils';

/*
  ⌘K command palette — keyboard-first quick consults and actions. Type a
  question and press Enter to send it, or pick a seeded consultation.
  Set as the paper's index: an ink sheet wipes down, the entries rise into
  place in the display face, and the one under the cursor comes up to full ink.
*/

const expo = [0.19, 1, 0.22, 1] as const;

interface Command {
  id: string;
  label: string;
  hint?: string;
  run: () => void;
}

interface Props {
  open: boolean;
  onClose: () => void;
  onSend: (query: string) => void;
  onReset: () => void;
  onToggleTheme: () => void;
}

export function CommandPalette({ open, onClose, onSend, onReset, onToggleTheme }: Props) {
  const [query, setQuery] = useState('');
  const [cursor, setCursor] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const commands = useMemo<Command[]>(() => {
    const seeds: Command[] = PROMPT_SEEDS.map((s) => ({
      id: s.id,
      label: s.title,
      hint: s.topic,
      run: () => onSend(s.query),
    }));
    const actions: Command[] = [
      { id: 'new', label: 'New consultation', run: onReset },
      { id: 'theme', label: 'Switch edition — Day / Night', run: onToggleTheme },
    ];
    return [...seeds, ...actions];
  }, [onSend, onReset, onToggleTheme]);

  const q = query.trim().toLowerCase();
  const filtered = q
    ? commands.filter((c) => (c.label + ' ' + (c.hint ?? '')).toLowerCase().includes(q))
    : commands;

  // A free-form "ask" row when the query doesn't match a command.
  const askRow = query.trim().length > 2;
  const rows = filtered.length + (askRow ? 1 : 0);

  useEffect(() => {
    if (open) {
      setQuery('');
      setCursor(0);
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  useEffect(() => setCursor(0), [query]);

  const choose = (index: number) => {
    if (askRow && index === 0) {
      onSend(query.trim());
    } else {
      const cmd = filtered[index - (askRow ? 1 : 0)];
      cmd?.run();
    }
    onClose();
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setCursor((c) => (c + 1) % Math.max(rows, 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setCursor((c) => (c - 1 + rows) % Math.max(rows, 1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      choose(cursor);
    } else if (e.key === 'Escape') {
      onClose();
    }
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-50 flex items-start justify-center px-3 pt-[9vh] sm:px-4 sm:pt-[11vh]"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0, transition: { duration: 0.25, delay: 0.1 } }}
        >
          <button
            aria-label="Close command palette"
            onClick={onClose}
            className="absolute inset-0 bg-desk/60 backdrop-blur-[2px]"
          />
          {/* The index, printed on an ink sheet that wipes down into place. */}
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-label="Command palette"
            initial={{ clipPath: 'inset(0 0 100% 0)' }}
            animate={{ clipPath: 'inset(0 0 0% 0)' }}
            exit={{ clipPath: 'inset(0 0 100% 0)' }}
            transition={{ duration: 0.55, ease: expo }}
            className="slab relative w-full max-w-2xl overflow-hidden rounded-[2px] shadow-[0_30px_80px_-30px_rgba(0,0,0,0.6)]"
          >
            <div className="flex items-center gap-3 border-b border-page/20 px-4 py-3.5 sm:px-5">
              <span className="head text-[1.1rem] leading-none text-page/60">Q.</span>
              <input
                ref={inputRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={onKeyDown}
                placeholder="Ask a question or jump to a consult…"
                className="flex-1 bg-transparent font-prose text-[1rem] text-page placeholder:text-page/45 focus:outline-none"
              />
              <kbd className="rounded-[2px] border border-page/25 px-1.5 py-0.5 font-mono text-[0.56rem] text-page/60">
                esc
              </kbd>
            </div>

            <ul className="max-h-[56vh] overflow-y-auto px-2 py-2 sm:px-3">
              {askRow && (
                <Row
                  no="→"
                  active={cursor === 0}
                  label={`Ask — “${query.trim()}”`}
                  hint="Enter"
                  i={0}
                  onMouseEnter={() => setCursor(0)}
                  onClick={() => choose(0)}
                />
              )}
              {filtered.map((c, i) => {
                const index = i + (askRow ? 1 : 0);
                return (
                  <Row
                    key={c.id}
                    no={String(i + 1).padStart(2, '0')}
                    active={cursor === index}
                    label={c.label}
                    hint={c.hint}
                    i={index}
                    onMouseEnter={() => setCursor(index)}
                    onClick={() => choose(index)}
                  />
                );
              })}
              {rows === 0 && (
                <li className="px-3 py-6 text-center font-prose text-sm italic text-page/60">
                  No matching consults.
                </li>
              )}
            </ul>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function Row({
  no,
  active,
  label,
  hint,
  i,
  onMouseEnter,
  onClick,
}: {
  no: string;
  active: boolean;
  label: string;
  hint?: string;
  i: number;
  onMouseEnter: () => void;
  onClick: () => void;
}) {
  return (
    <li className="overflow-hidden border-b border-page/10 last:border-b-0">
      <motion.button
        type="button"
        onMouseEnter={onMouseEnter}
        onClick={onClick}
        initial={{ y: '100%', opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.7, delay: 0.12 + Math.min(i, 8) * 0.04, ease: expo }}
        className={cn(
          'flex w-full items-baseline gap-3 px-2 py-2.5 text-left transition-colors duration-200 sm:gap-4 sm:py-3',
          active ? 'text-page' : 'text-page/50',
        )}
      >
        <span className="w-6 shrink-0 font-prose text-[0.8rem] italic">{no}</span>
        <span className="head flex-1 truncate text-[1.35rem] leading-[1.05] sm:text-[1.7rem]">{label}</span>
        {hint && (
          <span className="hidden font-mono text-[0.56rem] uppercase tracking-[0.12em] sm:inline">{hint}</span>
        )}
        <span
          className={cn('font-display text-[1.1rem] font-bold transition-all duration-300', active ? 'translate-x-0 opacity-100' : '-translate-x-2 opacity-0')}
          aria-hidden
        >
          →
        </span>
      </motion.button>
    </li>
  );
}

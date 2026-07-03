import { useEffect, useMemo, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { PROMPT_SEEDS } from '../lib/mockData';
import { Icon, type IconName } from './Icon';
import { cn } from '../lib/utils';

/*
  ⌘K command palette — keyboard-first quick consults and actions. Type a
  question and press Enter to send it, or pick a seeded consultation.
*/

interface Command {
  id: string;
  label: string;
  hint?: string;
  icon: IconName;
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
      icon: 'book',
      run: () => onSend(s.query),
    }));
    const actions: Command[] = [
      { id: 'new', label: 'New consultation', icon: 'plus', run: onReset },
      { id: 'theme', label: 'Toggle light / dark', icon: 'moon', run: onToggleTheme },
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
          className="fixed inset-0 z-50 flex items-start justify-center px-4 pt-[12vh]"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <button
            aria-label="Close command palette"
            onClick={onClose}
            className="absolute inset-0 bg-ink/30 backdrop-blur-[2px]"
          />
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-label="Command palette"
            initial={{ opacity: 0, y: -8, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.98 }}
            transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }}
            className="relative w-full max-w-xl overflow-hidden rounded-card border border-line-strong bg-surface-raised shadow-peek"
          >
            <div className="flex items-center gap-3 border-b border-line px-4 py-3">
              <Icon name="command" size={16} className="text-ink-faint" />
              <input
                ref={inputRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={onKeyDown}
                placeholder="Ask a question or jump to a consult…"
                className="flex-1 bg-transparent font-prose text-[0.98rem] text-ink placeholder:text-ink-faint focus:outline-none"
              />
              <kbd className="rounded-[3px] border border-line bg-surface px-1.5 py-0.5 font-mono text-[0.56rem] text-ink-faint">
                esc
              </kbd>
            </div>

            <ul className="max-h-[46vh] overflow-y-auto p-1.5">
              {askRow && (
                <Row
                  active={cursor === 0}
                  icon="send"
                  label={`Ask ARIA — “${query.trim()}”`}
                  hint="Enter"
                  onMouseEnter={() => setCursor(0)}
                  onClick={() => choose(0)}
                />
              )}
              {filtered.map((c, i) => {
                const index = i + (askRow ? 1 : 0);
                return (
                  <Row
                    key={c.id}
                    active={cursor === index}
                    icon={c.icon}
                    label={c.label}
                    hint={c.hint}
                    onMouseEnter={() => setCursor(index)}
                    onClick={() => choose(index)}
                  />
                );
              })}
              {rows === 0 && (
                <li className="px-3 py-6 text-center font-prose text-sm text-ink-faint">
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
  active,
  icon,
  label,
  hint,
  onMouseEnter,
  onClick,
}: {
  active: boolean;
  icon: IconName;
  label: string;
  hint?: string;
  onMouseEnter: () => void;
  onClick: () => void;
}) {
  return (
    <li>
      <button
        type="button"
        onMouseEnter={onMouseEnter}
        onClick={onClick}
        className={cn(
          'flex w-full items-center gap-3 rounded-[3px] px-3 py-2.5 text-left transition-colors',
          active ? 'bg-accent/12 text-ink' : 'text-ink-soft',
        )}
      >
        <span className={cn(active ? 'text-accent' : 'text-ink-faint')}>
          <Icon name={icon} size={15} />
        </span>
        <span className="flex-1 truncate font-prose text-[0.92rem]">{label}</span>
        {hint && (
          <span className="font-mono text-[0.56rem] uppercase tracking-[0.1em] text-ink-faint">
            {hint}
          </span>
        )}
      </button>
    </li>
  );
}

import type { SafetyNote } from '../lib/types';
import { Icon, type IconName } from './Icon';
import { cn } from '../lib/utils';

/*
  Safety / scope notes. Present and clear, never alarmist — a quiet oxblood
  hairline rather than a red warning box.
*/

const KIND: Record<SafetyNote['kind'], { icon: IconName; label: string }> = {
  scope: { icon: 'scope', label: 'Scope' },
  caution: { icon: 'caution', label: 'Caution' },
  interaction: { icon: 'link', label: 'Interaction' },
};

export function SafetyNotes({ notes }: { notes: SafetyNote[] }) {
  if (!notes.length) return null;
  return (
    <ul className="space-y-2">
      {notes.map((n, i) => {
        const meta = KIND[n.kind];
        return (
          <li
            key={i}
            className={cn(
              'flex gap-2.5 border-l-2 border-oxblood/50 bg-oxblood/[0.04] py-1.5 pl-2.5 pr-2',
            )}
          >
            <span className="mt-px text-oxblood/80">
              <Icon name={meta.icon} size={14} />
            </span>
            <span>
              <span className="font-mono text-[0.56rem] uppercase tracking-[0.12em] text-oxblood/90">
                {meta.label}
              </span>
              <span className="mt-0.5 block font-prose text-[0.82rem] leading-snug text-ink-soft">
                {n.text}
              </span>
            </span>
          </li>
        );
      })}
    </ul>
  );
}

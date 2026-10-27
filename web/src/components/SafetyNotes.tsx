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
  support: { icon: 'support', label: 'Support' },
};

export function SafetyNotes({ notes }: { notes: SafetyNote[] }) {
  if (!notes.length) return null;
  return (
    <ul className="space-y-2">
      {notes.map((n, i) => {
        const meta = KIND[n.kind];
        const support = n.kind === 'support';
        return (
          <li
            key={i}
            className={cn(
              'flex gap-2.5 rounded-r-[8px] border-l-2 py-2 pl-2.5 pr-3',
              /* Someone reading a helpline may be in crisis: the calm
                 evidence green, never the oxblood of a warning. */
              support
                ? 'border-tier-strong/50 bg-tier-strong/[0.06]'
                : 'border-oxblood/50 bg-oxblood/[0.05]',
            )}
          >
            <span className={cn('mt-px', support ? 'text-tier-strong/85' : 'text-oxblood/80')}>
              <Icon name={meta.icon} size={14} />
            </span>
            <span>
              <span
                className={cn(
                  'font-mono text-[0.56rem] uppercase tracking-[0.12em]',
                  support ? 'text-tier-strong' : 'text-oxblood/90',
                )}
              >
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

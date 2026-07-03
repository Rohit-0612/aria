import { motion } from 'framer-motion';
import { cn } from '../lib/utils';

/*
  Judge confidence as a calibrated arc gauge — instrument language, not a
  progress bar. Sweeps to its value once on reveal.
*/

interface Props {
  value: number; // 0..1
  size?: number;
  animate?: boolean;
}

export function ConfidenceGauge({ value, size = 46, animate = true }: Props) {
  const pct = Math.round(value * 100);
  const r = (size - 6) / 2;
  const cx = size / 2;
  const cy = size / 2;
  // 270° arc, starting bottom-left.
  const start = 135;
  const sweep = 270;
  const circumference = 2 * Math.PI * r;
  const arcLen = (sweep / 360) * circumference;
  const filled = (value * sweep) / 360 * circumference;

  const color =
    value >= 0.85 ? 'var(--tier-strong)' : value >= 0.6 ? 'var(--tier-moderate)' : 'var(--tier-limited)';

  return (
    <div
      className="relative grid place-items-center"
      style={{ width: size, height: size }}
      role="meter"
      aria-valuenow={pct}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={`Judge confidence ${pct} percent`}
    >
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={cx}
          cy={cy}
          r={r}
          fill="none"
          stroke="hsl(var(--line-strong) / 0.5)"
          strokeWidth={3}
          strokeLinecap="round"
          strokeDasharray={`${arcLen} ${circumference}`}
          transform={`rotate(${start} ${cx} ${cy})`}
        />
        <motion.circle
          cx={cx}
          cy={cy}
          r={r}
          fill="none"
          stroke={`hsl(${color})`}
          strokeWidth={3}
          strokeLinecap="round"
          strokeDasharray={`${filled} ${circumference}`}
          transform={`rotate(${start} ${cx} ${cy})`}
          initial={animate ? { strokeDasharray: `0 ${circumference}` } : false}
          animate={{ strokeDasharray: `${filled} ${circumference}` }}
          transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
        />
      </svg>
      <div className="absolute flex flex-col items-center leading-none">
        <span className={cn('font-mono text-[0.78rem] font-medium text-ink')}>{pct}</span>
      </div>
    </div>
  );
}

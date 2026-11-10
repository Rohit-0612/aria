import { useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';

/*
  The broadsheet's small motion vocabulary, shared across the surface:

    <Roll>        a label whose letters roll up to a fresh copy on hover
    <Doodle/>     a hand-drawn loop that inks itself around its host
    <RiseChars>   a word whose letters rise off the baseline like set type
    <CountUp>     a figure that counts up to its value once it is shown
*/

const expo = [0.19, 1, 0.22, 1] as const;

export function Roll({ children }: { children: string }) {
  return (
    <span className="roll">
      <span>{children}</span>
      <span aria-hidden>{children}</span>
    </span>
  );
}

/** Place inside an element with `.doodle-host`. */
export function Doodle() {
  return (
    <svg className="doodle" viewBox="0 0 400 130" preserveAspectRatio="none" aria-hidden>
      <path
        d="M34 74 C18 40 110 12 214 14 C318 16 392 40 384 72 C376 104 262 120 160 116 C70 112 14 96 22 66 C30 40 104 26 168 26"
        pathLength={1}
      />
    </svg>
  );
}

export function RiseChars({
  text,
  play = true,
  delay = 0,
  stagger = 0.045,
  duration = 1.2,
  reduced = false,
}: {
  text: string;
  play?: boolean;
  delay?: number;
  stagger?: number;
  duration?: number;
  reduced?: boolean;
}) {
  return (
    <span aria-label={text} className="inline-block whitespace-nowrap">
      {[...text].map((ch, i) => (
        <span key={i} aria-hidden className="inline-block overflow-hidden align-bottom">
          <motion.span
            className="inline-block"
            initial={reduced ? false : { y: '110%' }}
            animate={play || reduced ? { y: 0 } : { y: '110%' }}
            transition={reduced ? { duration: 0 } : { duration, delay: delay + i * stagger, ease: expo }}
          >
            {ch === ' ' ? ' ' : ch}
          </motion.span>
        </span>
      ))}
    </span>
  );
}

/** Counts from 0 to `value` once `play` is true. */
export function useCountUp(value: number, play = true, ms = 1600, reduced = false) {
  const [v, setV] = useState(reduced ? value : 0);
  const done = useRef(false);
  useEffect(() => {
    if (reduced) {
      setV(value);
      return;
    }
    if (!play || done.current) return;
    done.current = true;
    const t0 = performance.now();
    let raf = 0;
    const step = (now: number) => {
      const t = Math.min(1, (now - t0) / ms);
      setV(value * (1 - Math.pow(1 - t, 3)));
      if (t < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => {
      cancelAnimationFrame(raf);
      done.current = false;
    };
  }, [value, play, ms, reduced]);
  return v;
}

export function CountUp({
  value,
  decimals = 0,
  play = true,
  ms,
  reduced = false,
}: {
  value: number;
  decimals?: number;
  play?: boolean;
  ms?: number;
  reduced?: boolean;
}) {
  const v = useCountUp(value, play, ms, reduced);
  const text =
    decimals > 0 ? v.toFixed(decimals) : Math.round(v).toLocaleString('en-IN');
  return <span className="tabular-nums">{text}</span>;
}

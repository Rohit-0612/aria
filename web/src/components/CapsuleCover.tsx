import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { motion } from 'framer-motion';

/*
  The cover — ARIA, dispensed.

  On the ink ground the nameplate rises letter by letter. A capsule draws
  itself around it, so the name becomes the capsule's label: one half fills
  in vermilion, the other in newsprint. The capsule gives a small shake,
  then cracks open along its seam — the two halves slide away like doors,
  granules spill out, and the front page is there behind them.

  Any click or key skips straight to the opening.
*/

interface Props {
  reduced: boolean;
  /** The capsule starts to open: the app behind is coming into view. */
  onOpen: () => void;
  /** The halves are gone: unmount the cover. */
  onDone: () => void;
}

type Phase = 'build' | 'open';

const expo = [0.19, 1, 0.22, 1] as const;
const LETTERS = ['A', 'R', 'I', 'A'];
const OPEN_AT_MS = 3000;
const OPEN_AT_REDUCED_MS = 900;

export function CapsuleCover({ reduced, onOpen, onDone }: Props) {
  const [phase, setPhase] = useState<Phase>('build');
  const born = useRef(performance.now());
  const opened = useRef(false);

  const open = useCallback(() => {
    if (opened.current) return;
    opened.current = true;
    onOpen();
    setPhase('open');
  }, [onOpen]);

  useEffect(() => {
    const t = setTimeout(open, reduced ? OPEN_AT_REDUCED_MS : OPEN_AT_MS);
    return () => clearTimeout(t);
  }, [open, reduced]);

  useEffect(() => {
    if (phase !== 'open') return;
    const t = setTimeout(onDone, reduced ? 350 : 1500);
    return () => clearTimeout(t);
  }, [phase, reduced, onDone]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (['Enter', 'Escape', ' '].includes(e.key) && performance.now() - born.current > 400) open();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open]);

  // Reduced motion: the finished capsule, held for a beat, then a fade.
  if (reduced) {
    return (
      <motion.div
        className="edition-day slab fixed inset-0 z-[95] grid place-items-center"
        initial={{ opacity: 1 }}
        animate={{ opacity: phase === 'open' ? 0 : 1 }}
        transition={{ duration: 0.3 }}
      >
        <Scene settled />
      </motion.div>
    );
  }

  return (
    <div
      role="presentation"
      onClick={() => performance.now() - born.current > 400 && open()}
      className="edition-day fixed inset-0 z-[95] cursor-pointer overflow-hidden"
    >
      {phase === 'build' ? (
        <div className="slab absolute inset-0">
          <Scene />
        </div>
      ) : (
        <>
          {/* The same finished scene, cut down the capsule's seam into two
              doors that slide apart. */}
          <Door side="left" />
          <Door side="right" />
          <Granules />
        </>
      )}
    </div>
  );
}

function Door({ side }: { side: 'left' | 'right' }) {
  const left = side === 'left';
  return (
    <motion.div
      className={`slab absolute top-0 h-full w-1/2 overflow-hidden ${left ? 'left-0' : 'right-0'}`}
      initial={{ x: 0, rotate: 0 }}
      animate={{ x: left ? '-104%' : '104%', rotate: left ? -2.5 : 2.5 }}
      transition={{ duration: 1.25, ease: [0.76, 0, 0.24, 1], delay: 0.08 }}
      style={{ transformOrigin: left ? '100% 50%' : '0% 50%' }}
    >
      <div className={`absolute top-0 h-full w-screen ${left ? 'left-0' : 'right-0'}`}>
        <Scene settled />
      </div>
    </motion.div>
  );
}

/* The nameplate inside its capsule. `settled` renders the finished state with
   no entrance, for the doors and for reduced motion. */
function Scene({ settled = false }: { settled?: boolean }) {
  const t = (duration: number, delay: number) =>
    settled ? { duration: 0 } : { duration, delay, ease: expo };

  return (
    <div className="absolute inset-0 grid place-items-center">
      <div className="flex flex-col items-center [--cw:min(88vw,900px)]">
        <motion.div
          className="relative"
          style={{ width: 'var(--cw)', height: 'calc(var(--cw) * 0.36)' }}
          initial={false}
          animate={settled ? {} : { rotate: [0, 0, -2.2, 2.2, -1.2, 0] }}
          transition={settled ? {} : { duration: 0.6, delay: 2.35, times: [0, 0.01, 0.3, 0.6, 0.85, 1] }}
        >
          {/* Fills: vermilion from the left end, newsprint from the right. */}
          <div className="absolute inset-0 overflow-hidden rounded-full">
            <motion.div
              className="absolute inset-y-0 left-0 w-1/2 bg-accent"
              initial={settled ? false : { clipPath: 'inset(0 100% 0 0)' }}
              animate={{ clipPath: 'inset(0 0% 0 0)' }}
              transition={t(0.7, 1.55)}
            />
            <motion.div
              className="absolute inset-y-0 right-0 w-1/2 bg-page"
              initial={settled ? false : { clipPath: 'inset(0 0 0 100%)' }}
              animate={{ clipPath: 'inset(0 0 0 0%)' }}
              transition={t(0.7, 1.6)}
            />
            {/* Rounded-body shading and a glint along the top, so it reads
                as a gelatin shell rather than a flat sticker. */}
            <motion.div
              className="absolute inset-0"
              style={{
                background:
                  'linear-gradient(180deg, rgba(255,255,255,0.2) 0%, rgba(255,255,255,0) 32%, rgba(0,0,0,0) 62%, rgba(0,0,0,0.24) 100%)',
              }}
              initial={settled ? false : { opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={t(0.6, 1.95)}
            />
            <motion.div
              className="absolute left-[9%] right-[9%] top-[11%] h-[7%] rounded-full"
              style={{
                background:
                  'linear-gradient(90deg, rgba(255,255,255,0) 0%, rgba(255,255,255,0.5) 18%, rgba(255,255,255,0.32) 60%, rgba(255,255,255,0) 100%)',
              }}
              initial={settled ? false : { opacity: 0, scaleX: 0.4 }}
              animate={{ opacity: 1, scaleX: 1 }}
              transition={t(0.8, 2.05)}
            />
          </div>

          {/* The name, set twice and cut at the seam: newsprint on the
              vermilion half, ink on the newsprint half. */}
          <Name half="left" settled={settled} />
          <Name half="right" settled={settled} />

          {/* The seam. */}
          <motion.span
            className="absolute inset-y-0 left-1/2 w-[3px] -translate-x-1/2 bg-[hsl(var(--ink))]"
            initial={settled ? false : { scaleY: 0 }}
            animate={{ scaleY: 1 }}
            transition={t(0.5, 1.95)}
          />

          {/* The capsule's outline, drawn around the name. */}
          <svg
            className="pointer-events-none absolute inset-0 h-full w-full overflow-visible"
            viewBox="0 0 900 324"
            preserveAspectRatio="none"
            aria-hidden
          >
            <motion.rect
              x="1.5"
              y="1.5"
              width="897"
              height="321"
              rx="160.5"
              fill="none"
              stroke="hsl(var(--page))"
              strokeWidth="3"
              vectorEffect="non-scaling-stroke"
              initial={settled ? false : { pathLength: 0 }}
              animate={{ pathLength: 1 }}
              transition={t(1.1, 0.75)}
            />
          </svg>
        </motion.div>

        <motion.p
          className="mt-[calc(var(--cw)*0.07)] font-mono text-[clamp(0.55rem,1.1vw,0.72rem)] uppercase tracking-[0.3em] text-page/70"
          initial={settled ? false : { opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={t(0.9, 1.9)}
        >
          Retrieve · Rerank · Generate · Judge
        </motion.p>
      </div>
    </div>
  );
}

function Name({ half, settled }: { half: 'left' | 'right'; settled: boolean }) {
  const left = half === 'left';
  return (
    <motion.div
      aria-hidden={!left}
      aria-label={left ? 'ARIA' : undefined}
      className="head absolute inset-0 flex items-center justify-center leading-none"
      style={{
        fontSize: 'calc(var(--cw) * 0.3)',
        clipPath: left ? 'inset(0 50% 0 0)' : 'inset(0 0 0 50%)',
        paddingTop: '0.1em',
      }}
      initial={settled ? false : { color: 'hsl(var(--page))' }}
      animate={{ color: left ? 'hsl(var(--page))' : 'hsl(var(--ink))' }}
      transition={settled ? { duration: 0 } : { duration: 0.6, delay: 1.65 }}
    >
      {LETTERS.map((ch, i) => (
        <span key={i} className="inline-block overflow-hidden">
          <motion.span
            className="inline-block"
            initial={settled ? false : { y: '110%' }}
            animate={{ y: 0 }}
            transition={settled ? { duration: 0 } : { duration: 1.1, delay: 0.15 + i * 0.09, ease: expo }}
          >
            {ch}
          </motion.span>
        </span>
      ))}
    </motion.div>
  );
}

/* Powder and pellets spilling from the seam as the capsule opens. */
function Granules() {
  const bits = useMemo(
    () =>
      Array.from({ length: 34 }, (_, i) => {
        const side = i % 2 ? 1 : -1;
        const angle = (Math.random() * 1.6 - 0.8) * Math.PI * 0.5;
        const dist = 16 + Math.random() * 30;
        return {
          dx: side * Math.cos(angle) * dist * (0.4 + Math.random() * 0.6),
          dy: Math.sin(angle) * dist + (Math.random() * 10 - 2),
          size: 4 + Math.random() * 9,
          accent: Math.random() < 0.45,
          delay: Math.random() * 0.18,
          spin: Math.random() * 180 - 90,
          pill: Math.random() < 0.25,
        };
      }),
    [],
  );
  return (
    <div className="pointer-events-none absolute left-1/2 top-1/2">
      {bits.map((b, i) => (
        <motion.span
          key={i}
          className={`absolute block ${b.pill ? 'rounded-full' : 'rounded-[40%]'} ${
            b.accent ? 'bg-accent' : 'bg-page'
          } shadow-[0_0_0_1px_hsl(var(--ink)/0.25)]`}
          style={{ width: b.pill ? b.size * 1.9 : b.size, height: b.size, marginLeft: -b.size / 2, marginTop: -b.size / 2 }}
          initial={{ x: 0, y: 0, opacity: 0, scale: 0.4, rotate: 0 }}
          animate={{
            x: `${b.dx}vw`,
            y: `${b.dy}vh`,
            opacity: [0, 1, 1, 0],
            scale: [0.4, 1, 1, 0.8],
            rotate: b.spin,
          }}
          transition={{ duration: 1.3, delay: 0.05 + b.delay, ease: [0.16, 1, 0.3, 1], times: [0, 0.1, 0.7, 1] }}
        />
      ))}
    </div>
  );
}

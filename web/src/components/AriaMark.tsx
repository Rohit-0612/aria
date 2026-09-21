import { motion } from 'framer-motion';

/*
  ARIA's speaker mark — the colophon monogram in a ring, sitting in the
  gutter beside every reply. While the graph is running the ring breathes
  and a second, dashed ring turns slowly around it: the answer is being
  worked on, stated without a spinner.
*/

export function AriaMark({ size = 28, live = false }: { size?: number; live?: boolean }) {
  return (
    <span
      className="relative grid shrink-0 place-items-center"
      style={{ width: size, height: size }}
      aria-hidden
    >
      {live && (
        <>
          <motion.span
            className="absolute rounded-full border border-dashed border-accent/45"
            style={{ inset: -4 }}
            animate={{ rotate: 360 }}
            transition={{ duration: 9, repeat: Infinity, ease: 'linear' }}
          />
          <motion.span
            className="absolute rounded-full bg-accent/20"
            style={{ inset: 0 }}
            animate={{ scale: [1, 1.45, 1], opacity: [0.5, 0, 0.5] }}
            transition={{ duration: 2.2, repeat: Infinity, ease: 'easeInOut' }}
          />
        </>
      )}

      <span className="relative grid h-full w-full place-items-center rounded-full border border-accent/40 bg-accent/[0.09] text-accent">
        <svg
          width={size * 0.56}
          height={size * 0.56}
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={1.9}
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M6.4 18.4L12 4.6l5.6 13.8" />
          <path d="M8.6 13.9h6.8" />
        </svg>
      </span>
    </span>
  );
}

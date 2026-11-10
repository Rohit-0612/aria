import { useEffect, useRef } from 'react';
import { curtain } from '../lib/curtain';

/*
  Host elements for the paper curtain (lib/curtain.ts): the WebGL canvas,
  the flat-sheet fallback, and the label printed on the sheet mid-turn.
*/

export function Curtain() {
  const canvas = useRef<HTMLCanvasElement>(null);
  const fallback = useRef<HTMLDivElement>(null);
  const label = useRef<HTMLDivElement>(null);

  useEffect(() => {
    curtain.mount(canvas.current!, fallback.current!, label.current!);
  }, []);

  return (
    <>
      <canvas
        ref={canvas}
        aria-hidden
        className="pointer-events-none fixed inset-0 z-[90] h-screen w-screen"
      />
      <div
        ref={fallback}
        aria-hidden
        className="pointer-events-none fixed inset-0 z-[91] opacity-0"
      />
      <div
        ref={label}
        aria-hidden
        className="head pointer-events-none fixed inset-0 z-[93] grid place-items-center px-4 text-center text-[clamp(56px,13vw,200px)] opacity-0"
      />
    </>
  );
}

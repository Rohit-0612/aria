import { useEffect, useRef } from 'react';

/*
  A newspaper halftone plate, printed as ink dots on a canvas.

  The image is drawn procedurally (a capsule and a scored tablet — ARIA's
  subject matter, no photo asset needed), turned into an ink-density map and
  screened at 45° like real newsprint. The dots print in, in random order,
  the first time the plate is seen; near the pointer they swell and push
  aside, like a loupe moved across the page. Colours come from the design
  tokens, so the plate reprints itself when the edition changes.
*/

type Density = { w: number; h: number; d: Float32Array };

const SIZE = 360;

/** Pills, drawn white-on-black: white is where the ink goes. */
function drawPills(x: CanvasRenderingContext2D) {
  x.fillStyle = '#000';
  x.fillRect(0, 0, SIZE, SIZE);

  // Capsule, lying on the diagonal.
  x.save();
  x.translate(SIZE * 0.56, SIZE * 0.42);
  x.rotate(-0.62);
  const L = 230;
  const R = 50;
  const half = (dark: boolean) => {
    x.save();
    x.beginPath();
    if (dark) {
      x.moveTo(0, -R);
      x.lineTo(-L / 2 + R, -R);
      x.arc(-L / 2 + R, 0, R, -Math.PI / 2, Math.PI / 2, true);
      x.lineTo(0, R);
    } else {
      x.moveTo(0, -R);
      x.lineTo(L / 2 - R, -R);
      x.arc(L / 2 - R, 0, R, -Math.PI / 2, Math.PI / 2);
      x.lineTo(0, R);
    }
    x.closePath();
    const g = x.createLinearGradient(0, -R, 0, R);
    if (dark) {
      g.addColorStop(0, '#9a9a9a');
      g.addColorStop(0.28, '#5a5a5a');
      g.addColorStop(0.62, '#e6e6e6');
      g.addColorStop(1, '#ffffff');
    } else {
      g.addColorStop(0, '#2a2a2a');
      g.addColorStop(0.3, '#0c0c0c');
      g.addColorStop(0.7, '#5c5c5c');
      g.addColorStop(1, '#8a8a8a');
    }
    x.fillStyle = g;
    x.fill();
    x.lineWidth = 3;
    x.strokeStyle = '#d0d0d0';
    x.stroke();
    x.restore();
  };
  half(true);
  half(false);
  // The seam where the halves meet.
  x.fillStyle = '#ffffff';
  x.fillRect(-2, -R, 4, R * 2);
  x.restore();

  // A round scored tablet, lower left.
  x.save();
  x.translate(SIZE * 0.27, SIZE * 0.72);
  const T = 58;
  const tg = x.createRadialGradient(-T * 0.35, -T * 0.4, T * 0.1, 0, 0, T);
  tg.addColorStop(0, '#1a1a1a');
  tg.addColorStop(0.7, '#555');
  tg.addColorStop(1, '#bdbdbd');
  x.beginPath();
  x.arc(0, 0, T, 0, Math.PI * 2);
  x.fillStyle = tg;
  x.fill();
  x.lineWidth = 3;
  x.strokeStyle = '#d6d6d6';
  x.stroke();
  x.rotate(0.5);
  x.fillStyle = '#e0e0e0';
  x.fillRect(-T * 0.8, -2.5, T * 1.6, 5);
  x.restore();

  // A few loose granules.
  const dots: [number, number, number][] = [
    [0.78, 0.74, 9],
    [0.86, 0.66, 6],
    [0.7, 0.86, 5],
    [0.18, 0.3, 6],
    [0.12, 0.42, 4],
  ];
  x.fillStyle = '#bcbcbc';
  for (const [px, py, r] of dots) {
    x.beginPath();
    x.arc(px * SIZE, py * SIZE, r, 0, Math.PI * 2);
    x.fill();
  }
}

let cached: Density | null = null;
function density(): Density {
  if (cached) return cached;
  const c = document.createElement('canvas');
  c.width = SIZE;
  c.height = SIZE;
  const x = c.getContext('2d', { willReadFrequently: true })!;
  drawPills(x);
  const px = x.getImageData(0, 0, SIZE, SIZE).data;
  const d = new Float32Array(SIZE * SIZE);
  for (let i = 0; i < SIZE * SIZE; i++) d[i] = px[i * 4] / 255;
  cached = { w: SIZE, h: SIZE, d };
  return cached;
}

const cssColor = (el: Element, token: string) => {
  const probe = document.createElement('span');
  probe.style.color = `hsl(var(${token}))`;
  el.appendChild(probe);
  const c = getComputedStyle(probe).color;
  probe.remove();
  return c;
};

interface Props {
  className?: string;
  label: string;
  /** Dot pitch relative to the frame width; higher is a finer screen. */
  fineness?: number;
  /** Start printing only once this turns true (e.g. after the cover lifts). */
  play?: boolean;
}

export function Halftone({ className = '', label, fineness = 70, play = true }: Props) {
  const wrap = useRef<HTMLDivElement>(null);
  const cv = useRef<HTMLCanvasElement>(null);
  const playRef = useRef(play);
  const startRef = useRef<() => void>(() => {});

  useEffect(() => {
    playRef.current = play;
    if (play) startRef.current();
  }, [play]);

  useEffect(() => {
    const el = wrap.current!;
    const canvas = cv.current!;
    const ctx = canvas.getContext('2d')!;
    const rm = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const src = density();

    let W = 0;
    let H = 0;
    let dpr = 1;
    let cell = 6;
    let dots: { x: number; y: number; r: number; seed: number }[] = [];
    let bg = '';
    let ink = '';
    let printed = rm ? 1 : 0;
    let printing = false;
    let mx = -9999;
    let my = -9999;
    let inside = 0;
    let target = 0;
    let raf = 0;
    let visible = false;
    let alive = true;

    const colors = () => {
      bg = cssColor(el, '--surface');
      ink = cssColor(el, '--ink');
    };

    const build = () => {
      // Layout size, not the on-screen box: the plate may sit inside a sheet
      // that is still spinning in at 2% scale.
      W = Math.max(1, el.offsetWidth);
      H = Math.max(1, el.offsetHeight);
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.round(W * dpr);
      canvas.height = Math.round(H * dpr);
      cell = Math.max(3, Math.min(8, W / fineness));

      const s = Math.min(W / src.w, H / src.h) * 0.96;
      const toSrc = (x: number, y: number) => [src.w / 2 + (x - W / 2) / s, src.h / 2 + (y - H / 2) / s];
      dots = [];
      const cos = Math.cos(Math.PI / 4);
      const sin = Math.sin(Math.PI / 4);
      const diag = Math.hypot(W, H);
      let k = 0;
      for (let v = -diag; v <= diag; v += cell)
        for (let u = -diag; u <= diag; u += cell) {
          const x = W / 2 + u * cos - v * sin;
          const y = H / 2 + u * sin + v * cos;
          if (x < -cell || y < -cell || x > W + cell || y > H + cell) continue;
          const [sx, sy] = toSrc(x, y);
          if (sx < 0 || sy < 0 || sx > src.w - 2 || sy > src.h - 2) continue;
          const ix = Math.floor(sx);
          const iy = Math.floor(sy);
          const fx = sx - ix;
          const fy = sy - iy;
          const i0 = iy * src.w + ix;
          const D = src.d;
          const d =
            D[i0] * (1 - fx) * (1 - fy) +
            D[i0 + 1] * fx * (1 - fy) +
            D[i0 + src.w] * (1 - fx) * fy +
            D[i0 + src.w + 1] * fx * fy;
          if (d < 0.05) continue;
          dots.push({ x, y, r: cell * 0.62 * Math.sqrt(d), seed: ((k++ * 2654435761) % 1000) / 1000 });
        }
      draw(performance.now());
    };

    const draw = (t: number) => {
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.fillStyle = bg;
      ctx.fillRect(0, 0, W, H);
      ctx.fillStyle = ink;
      ctx.beginPath();
      const R = Math.max(60, W * 0.24);
      for (const p of dots) {
        let a = 1;
        if (printed < 1) {
          a = (printed * 1.25 - p.seed * 0.85) / 0.4;
          if (a <= 0) continue;
          if (a > 1) a = 1;
        }
        let { x, y } = p;
        let r = p.r * a;
        if (inside > 0.01) {
          const dx = x - mx;
          const dy = y - my;
          const f = Math.exp(-(dx * dx + dy * dy) / (R * R)) * inside;
          if (f > 0.002) {
            const dist = Math.hypot(dx, dy) || 1;
            x += (dx / dist) * f * cell * 1.4;
            y += (dy / dist) * f * cell * 1.4;
            r *= 1 + f * 0.85;
          }
          r *= 1 + 0.07 * inside * Math.sin(t * 0.003 + (p.x + p.y) * 0.035);
        }
        if (r < 0.25) continue;
        ctx.moveTo(x + r, y);
        ctx.arc(x, y, r, 0, Math.PI * 2);
      }
      ctx.fill();
    };

    const loop = (t: number) => {
      raf = 0;
      if (!alive) return;
      inside += (target - inside) * 0.12;
      if (Math.abs(target - inside) < 0.002) inside = target;
      draw(t);
      if ((printing || inside > 0.001 || target > 0) && visible) raf = requestAnimationFrame(loop);
    };
    const kick = () => {
      if (!raf && visible) raf = requestAnimationFrame(loop);
    };

    const startPrint = () => {
      if (printed >= 1 || printing || rm || !visible || !playRef.current) return;
      printing = true;
      const t0 = performance.now();
      const step = () => {
        printed = Math.min(1, (performance.now() - t0) / 1500);
        if (printed < 1 && alive) requestAnimationFrame(step);
        else printing = false;
      };
      requestAnimationFrame(step);
      kick();
    };
    startRef.current = startPrint;

    const io = new IntersectionObserver(
      ([e]) => {
        visible = e.isIntersecting;
        if (visible) {
          startPrint();
          kick();
        }
      },
      { threshold: 0.15 },
    );
    const move = (e: PointerEvent) => {
      const r = el.getBoundingClientRect();
      mx = ((e.clientX - r.left) / Math.max(1, r.width)) * W;
      my = ((e.clientY - r.top) / Math.max(1, r.height)) * H;
      target = 1;
      kick();
    };
    const leave = () => {
      target = 0;
      kick();
    };
    // Reprint in the other ink when the edition changes.
    const mo = new MutationObserver(() => {
      colors();
      draw(performance.now());
    });
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });

    colors();
    const ro = new ResizeObserver(build);
    ro.observe(el);
    io.observe(el);
    if (!rm) {
      el.addEventListener('pointermove', move);
      el.addEventListener('pointerleave', leave);
    }
    return () => {
      alive = false;
      cancelAnimationFrame(raf);
      io.disconnect();
      ro.disconnect();
      mo.disconnect();
      el.removeEventListener('pointermove', move);
      el.removeEventListener('pointerleave', leave);
    };
  }, [fineness]);

  return (
    <div ref={wrap} role="img" aria-label={label} className={`relative ${className}`}>
      <canvas ref={cv} aria-hidden className="absolute inset-0 h-full w-full" />
    </div>
  );
}

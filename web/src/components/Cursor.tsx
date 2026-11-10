import { useEffect, useRef } from 'react';

/*
  Pointer furniture, desktop only (fine pointer + hover).

  - An ink badge follows the pointer over anything marked `data-cursor="Label"`
    and names what a click will do — "Ask ↗" on a consult, "Read ↗" on a
    source. The system cursor stays as it is; the badge only adds a word.
  - Elements marked `data-magnetic` lean toward the pointer while it is over
    them and spring back when it leaves. Put it on a wrapper, never on an
    element whose transform is already animated.
*/

export function Cursor() {
  const badge = useRef<HTMLDivElement>(null);
  const text = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const fine = window.matchMedia('(hover: hover) and (pointer: fine)').matches;
    const rm = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (!fine) return;
    const b = badge.current!;
    const t = text.current!;

    let x = -200;
    let y = -200;
    let bx = x;
    let by = y;
    let raf = 0;
    let label = '';

    // Magnetic elements, each easing toward its own target offset.
    const mags = new Map<HTMLElement, { x: number; y: number; tx: number; ty: number }>();

    const frame = () => {
      raf = 0;
      bx += (x - bx) * 0.22;
      by += (y - by) * 0.22;
      b.style.transform = `translate3d(${bx}px, ${by}px, 0)`;
      let moving = Math.abs(x - bx) > 0.3 || Math.abs(y - by) > 0.3;
      mags.forEach((m, el) => {
        m.x += (m.tx - m.x) * 0.16;
        m.y += (m.ty - m.y) * 0.16;
        el.style.transform = `translate3d(${m.x.toFixed(2)}px, ${m.y.toFixed(2)}px, 0)`;
        if (Math.abs(m.tx - m.x) > 0.1 || Math.abs(m.ty - m.y) > 0.1) moving = true;
        else if (m.tx === 0 && m.ty === 0) {
          el.style.transform = '';
          mags.delete(el);
        }
      });
      if (moving) raf = requestAnimationFrame(frame);
    };
    const kick = () => {
      if (!raf) raf = requestAnimationFrame(frame);
    };

    const setLabel = (next: string) => {
      if (next === label) return;
      label = next;
      if (next) t.textContent = next;
      b.classList.toggle('is-on', !!next);
    };

    const move = (e: PointerEvent) => {
      x = e.clientX;
      y = e.clientY;
      const target = e.target as Element | null;
      const hit = target?.closest<HTMLElement>('[data-cursor]');
      if (!label && hit) {
        // Appear where the pointer is, not slide in from the last spot.
        bx = x;
        by = y;
      }
      setLabel(hit?.dataset.cursor ?? '');

      if (!rm) {
        const mag = target?.closest<HTMLElement>('[data-magnetic]') ?? null;
        mags.forEach((m, el) => {
          if (el !== mag) {
            m.tx = 0;
            m.ty = 0;
          }
        });
        if (mag) {
          const r = mag.getBoundingClientRect();
          const s = parseFloat(mag.dataset.magnetic || '0.3');
          const m = mags.get(mag) ?? { x: 0, y: 0, tx: 0, ty: 0 };
          m.tx = (x - (r.left + r.width / 2)) * s;
          m.ty = (y - (r.top + r.height / 2)) * s;
          mags.set(mag, m);
        }
      }
      kick();
    };
    const down = () => b.classList.add('is-down');
    const up = () => b.classList.remove('is-down');
    const leave = () => setLabel('');
    // Content can scroll under a still pointer.
    const recheck = () => {
      const el = document.elementFromPoint(x, y);
      setLabel(el?.closest<HTMLElement>('[data-cursor]')?.dataset.cursor ?? '');
    };

    // A click usually changes what is under the pointer (a consult asked, a
    // page turned): drop the badge until the pointer moves again.
    const click = () => setLabel('');

    window.addEventListener('pointermove', move, { passive: true });
    window.addEventListener('pointerdown', down);
    window.addEventListener('pointerup', up);
    window.addEventListener('wheel', recheck, { passive: true });
    window.addEventListener('click', click);
    document.addEventListener('pointerleave', leave);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerdown', down);
      window.removeEventListener('pointerup', up);
      window.removeEventListener('wheel', recheck);
      window.removeEventListener('click', click);
      document.removeEventListener('pointerleave', leave);
      mags.forEach((_, el) => (el.style.transform = ''));
    };
  }, []);

  return (
    <div ref={badge} className="cursor-badge" aria-hidden>
      <span ref={text} />
    </div>
  );
}

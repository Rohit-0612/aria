import { useEffect, useState } from 'react';

/**
 * Publishes the *visual* viewport height as `--app-h`.
 *
 * On iOS the layout viewport does not shrink when the keyboard opens, so a
 * `100dvh` app shell pushes its docked composer underneath the keyboard. The
 * visual viewport does shrink, so we track it and let the shell size itself
 * from that instead.
 */
export function useAppHeight() {
  useEffect(() => {
    const vv = window.visualViewport;
    const apply = () => {
      const h = vv?.height ?? window.innerHeight;
      document.documentElement.style.setProperty('--app-h', `${Math.round(h)}px`);
    };
    apply();
    vv?.addEventListener('resize', apply);
    vv?.addEventListener('scroll', apply);
    window.addEventListener('resize', apply);
    window.addEventListener('orientationchange', apply);
    return () => {
      vv?.removeEventListener('resize', apply);
      vv?.removeEventListener('scroll', apply);
      window.removeEventListener('resize', apply);
      window.removeEventListener('orientationchange', apply);
    };
  }, []);
}

/** Reactive `matchMedia`, for the few places CSS breakpoints can't reach. */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(
    () => typeof window !== 'undefined' && window.matchMedia(query).matches,
  );

  useEffect(() => {
    const mq = window.matchMedia(query);
    const onChange = () => setMatches(mq.matches);
    onChange();
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, [query]);

  return matches;
}

/** True on touch-first devices, where hover affordances never fire. */
export const useIsTouch = () => useMediaQuery('(hover: none)');

/** True from Tailwind's `sm` breakpoint up. */
export const useIsDesktop = () => useMediaQuery('(min-width: 640px)');

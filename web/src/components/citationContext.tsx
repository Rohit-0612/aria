import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';
import type { Citation } from '../lib/types';

/*
  Links an answer's inline citation markers to its source rail. Hovering a
  marker highlights the matching chip (and vice-versa); clicking one opens
  the rail and reveals that passage inline, so evidence is always one tap
  away without turning the reply into a bibliography.
*/

interface CitationCtx {
  byMarker: Map<number, Citation>;
  /** Marker under the pointer / focus, highlighted on both sides. */
  active: number | null;
  setActive: (n: number | null) => void;
  /** Is the source rail expanded under the answer? */
  railOpen: boolean;
  setRailOpen: (v: boolean | ((prev: boolean) => boolean)) => void;
  /** Which passage is expanded inside the rail. */
  opened: number | null;
  setOpened: (n: number | null) => void;
  /** Open the rail and reveal one passage — what a marker click does. */
  reveal: (marker: number) => void;
}

const Ctx = createContext<CitationCtx | null>(null);

export function CitationProvider({
  citations,
  children,
}: {
  citations: Citation[];
  children: ReactNode;
}) {
  const [active, setActive] = useState<number | null>(null);
  const [railOpen, setRailOpen] = useState(false);
  const [opened, setOpened] = useState<number | null>(null);

  const reveal = useCallback((marker: number) => {
    setRailOpen(true);
    setOpened((prev) => (prev === marker ? prev : marker));
  }, []);

  const value = useMemo<CitationCtx>(
    () => ({
      byMarker: new Map(citations.map((c) => [c.marker, c])),
      active,
      setActive,
      railOpen,
      setRailOpen,
      opened,
      setOpened,
      reveal,
    }),
    [citations, active, railOpen, opened, reveal],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useCitations(): CitationCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useCitations must be used within CitationProvider');
  return ctx;
}

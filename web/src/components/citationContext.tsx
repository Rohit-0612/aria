import { createContext, useContext, useMemo, useState, type ReactNode } from 'react';
import type { Citation } from '../lib/types';

/*
  Links an answer's inline citation markers to its margin rail. Hovering or
  focusing a marker highlights the matching source card (and vice-versa),
  and opening a marker can request the rail scroll it into view.
*/

interface CitationCtx {
  byMarker: Map<number, Citation>;
  active: number | null;
  setActive: (n: number | null) => void;
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
  const value = useMemo<CitationCtx>(
    () => ({
      byMarker: new Map(citations.map((c) => [c.marker, c])),
      active,
      setActive,
    }),
    [citations, active],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useCitations(): CitationCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useCitations must be used within CitationProvider');
  return ctx;
}

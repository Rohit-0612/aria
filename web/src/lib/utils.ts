/** Tiny className joiner — no dependency needed for our scale. */
export function cn(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(' ');
}

export function uid(prefix = 'id'): string {
  return `${prefix}-${Math.random().toString(36).slice(2, 9)}`;
}

/** Parse `[[3]]` citation markers out of a prose run. */
export interface ProseSegment {
  text: string;
  marker?: number;
}

export function parseCitations(text: string): ProseSegment[] {
  const segments: ProseSegment[] = [];
  const re = /\[\[(\d+)\]\]/g;
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text))) {
    if (m.index > last) segments.push({ text: text.slice(last, m.index) });
    segments.push({ text: '', marker: Number(m[1]) });
    last = m.index + m[0].length;
  }
  if (last < text.length) segments.push({ text: text.slice(last) });
  return segments;
}

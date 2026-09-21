import { Fragment, type ReactNode } from 'react';
import { CitationMarker } from './CitationMarker';

/*
  Dependency-free markdown for clinical prose, parsed line-by-line so mixed
  blocks (a heading immediately followed by text and bullets) render correctly:
  headings (#..######), thematic breaks (---), unordered lists (-, *, +),
  ordered lists (1. / 1)), GitHub tables, **bold**, *italic*, backslash
  escapes, and [[n]] citation markers. Typeset for the journal: section
  subheads in small caps, numbered journal tables.

  Anything this parser does not recognise is printed verbatim, so every gap
  in it surfaces as literal punctuation sitting in the middle of clinical
  prose. Three such gaps were reaching readers:

    ---     a thematic break fell through to a paragraph and printed as a
            row of hyphens (the generator emits these between sections).
    \*      a backslash-escaped asterisk printed the backslash, because
            escapes were never consumed (`\*All doses are with meals`).
    <br>    models emit these inside table cells; with no handling the tag
            itself was printed as text.

  Handled here rather than upstream: the generator is free to write ordinary
  Markdown, and the renderer is the one place that decides how it looks.
*/

/*
  Characters to fold before rendering.

  The prose face is Spectral, whose Google Fonts latin subset has no
  subscripts or superscripts, so "AT₁" fell back — and where the fallback
  chain has no glyph either, the reader gets a tofu box mid-sentence. The
  underlying textbook writes these as plain "AT1", so folding matches the
  source rather than inventing anything. The narrow no-break space (U+202F,
  30+ per answer) and non-breaking hyphen (U+2011) are folded to their plain
  equivalents for the same reason: invisible or box-rendered, never useful.

  Typographic characters that fonts DO cover — – — " " … ≥ ≤ → ↑ ↓ ² ³ — are
  deliberately left alone.
*/
const FOLD: Record<string, string> = {
  '\u202f': ' ', // narrow no-break space
  '\u00a0': ' ', // no-break space
  '\u2011': '-', // non-breaking hyphen
  '\u2080': '0', '\u2081': '1', '\u2082': '2', '\u2083': '3', '\u2084': '4',
  '\u2085': '5', '\u2086': '6', '\u2087': '7', '\u2088': '8', '\u2089': '9',
  '\u207a': '+', '\u207b': '-',
};

const FOLD_RE = new RegExp(`[${Object.keys(FOLD).join('')}]`, 'g');

/** Fold characters the prose face cannot draw. Never changes wording. */
function fold(text: string): string {
  return text.replace(FOLD_RE, (c) => FOLD[c] ?? c);
}

/*
  Order matters: the escape branch is first so `\*` is consumed before the
  emphasis branches can treat the asterisk as markup. `<br>` becomes a real
  line break, and a few stray inline tags are dropped rather than printed —
  models reach for them inside table cells, where a literal tag is both
  wrong and ugly. Note `<[a-zA-Z/]` cannot match a comparison like `<30`.
*/
const INLINE =
  /\\(.)|<br\s*\/?>|<\/?(?:b|i|u|em|strong|sub|sup|span|p|div|code)(?:\s[^>]*)?\/?>|\*\*(.+?)\*\*|__(.+?)__|\*(.+?)\*|\[\[(\d+)\]\]/gi;

function renderInline(raw: string, keyBase: string): ReactNode[] {
  const text = fold(raw);
  const out: ReactNode[] = [];
  const re = new RegExp(INLINE.source, 'gi');
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(<Fragment key={`${keyBase}-t${i}`}>{text.slice(last, m.index)}</Fragment>);
    if (m[1] !== undefined) {
      // Escaped character: print the character, drop the backslash.
      out.push(<Fragment key={`${keyBase}-e${i}`}>{m[1]}</Fragment>);
    } else if (/^<br/i.test(m[0])) {
      out.push(<br key={`${keyBase}-br${i}`} />);
    } else if (m[0].startsWith('<')) {
      // A stray inline tag: drop it, keep the text around it.
    } else if (m[2] !== undefined || m[3] !== undefined) {
      out.push(
        <strong key={`${keyBase}-b${i}`} className="font-semibold text-ink">
          {m[2] ?? m[3]}
        </strong>,
      );
    } else if (m[4] !== undefined) {
      out.push(
        <em key={`${keyBase}-i${i}`} className="italic">
          {m[4]}
        </em>,
      );
    } else if (m[5] !== undefined) {
      out.push(<CitationMarker key={`${keyBase}-c${i}`} marker={Number(m[5])} />);
    }
    last = m.index + m[0].length;
    i++;
  }
  if (last < text.length) out.push(<Fragment key={`${keyBase}-end`}>{text.slice(last)}</Fragment>);
  return out;
}

type Align = 'left' | 'center' | 'right';
interface ParsedTable {
  header: string[];
  rows: string[][];
  align: Align[];
}

const splitRow = (line: string): string[] => {
  const cells = line.split('|');
  if (cells.length && cells[0].trim() === '') cells.shift();
  if (cells.length && cells[cells.length - 1].trim() === '') cells.pop();
  return cells.map((c) => c.trim());
};

const SEP = /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/;

function parseTable(lines: string[]): ParsedTable | null {
  if (lines.length < 2 || !lines[0].includes('|') || !SEP.test(lines[1])) return null;
  const header = splitRow(lines[0]);
  const align: Align[] = splitRow(lines[1]).map((c) => {
    const l = c.startsWith(':');
    const r = c.endsWith(':');
    return l && r ? 'center' : r ? 'right' : 'left';
  });
  const rows = lines.slice(2).map(splitRow);
  return { header, rows, align };
}

interface UlItem {
  indent: number;
  text: string;
}

type Block =
  | { kind: 'heading'; level: number; text: string }
  | { kind: 'hr' }
  | { kind: 'ul'; items: UlItem[] }
  | { kind: 'ol'; items: { num: string; text: string }[] }
  | { kind: 'table'; table: ParsedTable }
  | { kind: 'p'; text: string };

const UL = /^[-*+]\s+(.*)$/;
const OL = /^(\d+)[.)]\s+(.*)$/;
const HEAD = /^(#{1,6})\s+(.*)$/;
// A thematic break. Cannot collide with a list item (those need a space
// after the marker) or a table separator (those contain a pipe).
const HR = /^(?:-{3,}|\*{3,}|_{3,})$/;

function tokenize(content: string): Block[] {
  const lines = content.replace(/\r/g, '').split('\n');
  const blocks: Block[] = [];
  let para: string[] = [];
  const flush = () => {
    if (para.length) blocks.push({ kind: 'p', text: para.join(' ') });
    para = [];
  };

  let i = 0;
  while (i < lines.length) {
    const raw = lines[i];
    const t = raw.trim();

    if (t === '') {
      flush();
      i++;
      continue;
    }

    const h = t.match(HEAD);
    if (h) {
      flush();
      blocks.push({ kind: 'heading', level: h[1].length, text: h[2].replace(/#+\s*$/, '').trim() });
      i++;
      continue;
    }

    if (HR.test(t)) {
      flush();
      blocks.push({ kind: 'hr' });
      i++;
      continue;
    }

    // Table: a pipe row immediately followed by a separator row.
    if (raw.includes('|') && i + 1 < lines.length && SEP.test(lines[i + 1])) {
      const tbl = [raw, lines[i + 1]];
      let j = i + 2;
      while (j < lines.length && lines[j].includes('|') && lines[j].trim() !== '') {
        tbl.push(lines[j]);
        j++;
      }
      const parsed = parseTable(tbl);
      if (parsed) {
        flush();
        blocks.push({ kind: 'table', table: parsed });
        i = j;
        continue;
      }
    }

    if (UL.test(t)) {
      flush();
      const items: UlItem[] = [];
      while (i < lines.length && UL.test(lines[i].trim())) {
        const lead = (lines[i].match(/^[ \t]*/)?.[0] ?? '').replace(/\t/g, '  ').length;
        items.push({ indent: lead, text: lines[i].trim().match(UL)![1] });
        i++;
      }
      blocks.push({ kind: 'ul', items });
      continue;
    }

    if (OL.test(t)) {
      flush();
      const items: { num: string; text: string }[] = [];
      while (i < lines.length && OL.test(lines[i].trim())) {
        const m = lines[i].trim().match(OL)!;
        items.push({ num: m[1], text: m[2] });
        i++;
      }
      blocks.push({ kind: 'ol', items });
      continue;
    }

    para.push(t);
    i++;
  }
  flush();
  return blocks;
}

export function Prose({ content, streaming }: { content: string; streaming?: boolean }) {
  const blocks = tokenize(content);
  let tableNo = 0;

  return (
    <div className="font-prose text-[0.96rem] leading-[1.68] text-ink-soft sm:text-[1.01rem] sm:leading-[1.75]">
      {blocks.map((b, bi) => {
        switch (b.kind) {
          case 'heading': {
            if (b.level <= 2) {
              return (
                <h4
                  key={bi}
                  className="mb-1.5 mt-5 font-display text-[1.1rem] font-semibold leading-snug tracking-tight2 text-ink first:mt-0"
                >
                  {renderInline(b.text, `h-${bi}`)}
                </h4>
              );
            }
            return (
              <p
                key={bi}
                className="sec mb-2 mt-5 !text-[0.64rem] !tracking-[0.16em] text-ink first:mt-0"
              >
                {renderInline(b.text, `h-${bi}`)}
              </p>
            );
          }

          case 'hr':
            return <hr key={bi} className="my-5 border-0 border-t border-line" />;

          case 'ul':
            return (
              <div key={bi} className="my-3.5">
                <NestedList nodes={buildTree(b.items)} keyBase={`ul-${bi}`} />
              </div>
            );

          case 'ol':
            return (
              <ol key={bi} className="my-3.5 space-y-1.5">
                {b.items.map((it, li) => (
                  <li key={li} className="relative pl-7">
                    <span className="absolute left-0 top-0 font-mono text-[0.72rem] tabular-nums text-accent">
                      {it.num}.
                    </span>
                    {renderInline(it.text, `ol-${bi}-${li}`)}
                  </li>
                ))}
              </ol>
            );

          case 'table': {
            tableNo += 1;
            return <ClinicalTable key={bi} table={b.table} index={bi} number={tableNo} />;
          }

          case 'p': {
            const isLast = bi === blocks.length - 1;
            return (
              <p key={bi} lang="en" className="my-3.5 first:mt-0">
                {renderInline(b.text, `p-${bi}`)}
                {streaming && isLast && <Caret />}
              </p>
            );
          }
        }
      })}
      {streaming && blocks[blocks.length - 1]?.kind !== 'p' && <Caret />}
    </div>
  );
}

interface TreeNode {
  text: string;
  children: TreeNode[];
}

/** Convert flat indent-tagged bullets into a nested tree. */
function buildTree(items: UlItem[]): TreeNode[] {
  const root: TreeNode = { text: '', children: [] };
  const stack: { node: TreeNode; indent: number }[] = [{ node: root, indent: -1 }];
  for (const it of items) {
    const node: TreeNode = { text: it.text, children: [] };
    while (stack.length > 1 && it.indent <= stack[stack.length - 1].indent) stack.pop();
    stack[stack.length - 1].node.children.push(node);
    stack.push({ node, indent: it.indent });
  }
  return root.children;
}

function NestedList({ nodes, keyBase }: { nodes: TreeNode[]; keyBase: string }) {
  return (
    <ul className="space-y-1.5">
      {nodes.map((n, i) => (
        <li key={i} className="relative pl-6">
          <span className="absolute left-0 top-0 font-mono text-[0.8rem] text-accent">—</span>
          {renderInline(n.text, `${keyBase}-${i}`)}
          {n.children.length > 0 && (
            <div className="mt-1.5">
              <NestedList nodes={n.children} keyBase={`${keyBase}-${i}`} />
            </div>
          )}
        </li>
      ))}
    </ul>
  );
}

function ClinicalTable({
  table,
  index,
  number,
}: {
  table: ParsedTable;
  index: number;
  number: number;
}) {
  const alignClass = (a: Align) =>
    a === 'right' ? 'text-right' : a === 'center' ? 'text-center' : 'text-left';

  return (
    <figure className="my-5">
      <figcaption className="label mb-1.5">Table {number}</figcaption>
      <div className="overflow-x-auto rounded-[10px] border border-line bg-surface/40">
        <table className="w-full border-collapse text-[0.88rem]">
          <thead>
            <tr className="border-b border-line-strong/60 bg-surface/70">
              {table.header.map((h, i) => (
                <th
                  key={i}
                  className={`px-3 py-2 font-mono text-[0.6rem] font-semibold uppercase tracking-[0.1em] text-ink ${alignClass(
                    table.align[i] ?? 'left',
                  )}`}
                >
                  {renderInline(h, `th-${index}-${i}`)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {table.rows.map((row, ri) => (
              <tr key={ri} className="border-b border-line last:border-b-0">
                {row.map((cell, ci) => (
                  <td
                    key={ci}
                    className={`px-3 py-2 align-top leading-snug text-ink-soft ${alignClass(
                      table.align[ci] ?? 'left',
                    )}`}
                  >
                    {renderInline(cell, `td-${index}-${ri}-${ci}`)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </figure>
  );
}

function Caret() {
  return (
    <span
      aria-hidden
      className="ml-0.5 inline-block h-[1.05em] w-[2px] translate-y-[0.15em] animate-pulse bg-accent"
    />
  );
}

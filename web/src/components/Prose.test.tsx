import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import type { Citation } from '../lib/types';
import { CitationProvider } from './citationContext';
import { Prose, holdPartialMarker, tokenize } from './Prose';

/*
  The renderer prints anything it does not recognise verbatim, so every gap
  in it reaches a reader as stray punctuation in clinical prose. These pin
  the shapes the generator actually emits.
*/

const cite = (marker: number): Citation => ({
  id: `c${marker}`,
  marker,
  book: 'dipiro',
  source: "DiPiro's Pharmacotherapy",
  section: 'A Pathophysiologic Approach, 12e',
  page: `p. ${100 + marker}`,
  snippet: `passage ${marker}`,
  relevance: 0.9,
  tier: 'strong',
});

function html(content: string, markers: number[] = [1, 2, 3], streaming = false): string {
  return renderToStaticMarkup(
    <CitationProvider citations={markers.map(cite)}>
      <Prose content={content} streaming={streaming} />
    </CitationProvider>,
  );
}

/** What the reader sees: the markup with every tag removed. */
const textOf = (out: string): string => out.replace(/<[^>]+>/g, '');

/** Visible superscript numerals, in order. */
const markersIn = (out: string): string[] =>
  [...out.matchAll(/aria-label="Source (\d+):/g)].map((m) => m[1]);

describe('blockquotes', () => {
  it('renders "> **Note:**" as a quote, not a literal bracket', () => {
    const out = html('Answer.\n\n> **Note:** verify against current guidelines.');
    expect(out).toContain('<blockquote');
    expect(out).toContain('<strong class="font-semibold text-ink">Note:</strong>');
    expect(out).not.toContain('&gt;');
  });

  it('joins consecutive quote lines and splits on a bare ">"', () => {
    const blocks = tokenize('> one\n> two\n>\n> three');
    expect(blocks).toEqual([{ kind: 'quote', paragraphs: ['one two', 'three'] }]);
  });

  it('leaves a comparison at the start of a line alone', () => {
    expect(tokenize('> 140 mm Hg is stage 2')[0].kind).toBe('p');
    expect(tokenize('>= 60 mL/min')[0].kind).toBe('p');
  });
});

describe('citation markers', () => {
  it('resolves [[n]] to its passage', () => {
    const out = html('Thiazides are first-line [[2]].');
    expect(markersIn(out)).toEqual(['2']);
    expect(textOf(out)).toBe('Thiazides are first-line2.');
  });

  it('sets adjacent markers as one comma-separated group, not "13"', () => {
    const out = html('ACE inhibitors reduce albuminuria [[1]][[3]].');
    expect(markersIn(out)).toEqual(['1', '3']);
    expect(out).toMatch(/Source 1:.*>,<\/span>.*Source 3:/s);
  });

  it('accepts the [[1, 3]] form and drops duplicates', () => {
    expect(markersIn(html('x [[1, 3]][[3]]'))).toEqual(['1', '3']);
  });

  it('drops markers that point at no retrieved passage', () => {
    const out = html('Claim [[9]]. Other [[1]][[7]].', [1]);
    expect(markersIn(out)).toEqual(['1']);
    expect(textOf(out)).toBe('Claim. Other1.');
  });

  it('resolves markers inside table cells', () => {
    const out = html('| Drug | Note |\n|---|---|\n| Lisinopril | ACEI [[1]] |');
    expect(out).toContain('<table');
    expect(markersIn(out)).toEqual(['1']);
  });
});

describe('streaming', () => {
  it.each([
    ['ACEIs help [', 'ACEIs help '],
    ['ACEIs help [[', 'ACEIs help '],
    ['ACEIs help [[1', 'ACEIs help '],
    ['ACEIs help [[1]', 'ACEIs help '],
    ['ACEIs help [[1]][[', 'ACEIs help [[1]]'],
  ])('holds back the unfinished marker in %j', (partial, shown) => {
    expect(holdPartialMarker(partial)).toBe(shown);
  });

  it('never holds back a finished marker', () => {
    expect(holdPartialMarker('ACEIs help [[1]]')).toBe('ACEIs help [[1]]');
  });

  it('prints no raw brackets mid-stream', () => {
    expect(textOf(html('ACEIs help [[1', [1], true))).toBe('ACEIs help');
  });
});

describe('existing shapes still render', () => {
  it('turns --- into a rule and consumes escapes', () => {
    const out = html('a\n\n---\n\n\\*All doses with meals');
    expect(out).toContain('<hr');
    expect(out).toContain('*All doses with meals');
    expect(out).not.toContain('\\');
  });
});

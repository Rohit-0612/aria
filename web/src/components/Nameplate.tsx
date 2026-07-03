import { Icon } from './Icon';

/*
  The journal nameplate — front matter at the head of the page. Set like the
  masthead of a printed clinical journal: identifier line, grand title,
  statement of scope, framed by the classic double rule.
*/

export function Nameplate() {
  return (
    <header className="mb-10">
      <div className="flex items-end justify-between gap-4 border-b border-rule/40 pb-2">
        <span className="ident">ISSN 2026·ARIA · Vol. 1 · No. 4</span>
        <span className="ident hidden sm:inline">Evidence-Graded · Peer-Adjudicated</span>
        <span className="ident">Open Access</span>
      </div>

      <div className="flex flex-col items-center pt-7 text-center">
        <span className="mb-3 text-accent">
          <Icon name="aria" size={30} strokeWidth={1.4} />
        </span>
        <h1 className="font-display text-[3.2rem] font-semibold leading-none tracking-[-0.03em] text-ink sm:text-[4.6rem]">
          ARIA
        </h1>
        <p className="mt-3 font-prose text-[0.95rem] italic text-ink-soft sm:text-[1.05rem]">
          The Journal of Evidence-Grounded Pharmacotherapy
        </p>
        <p className="mt-2 max-w-md font-mono text-[0.6rem] uppercase tracking-[0.18em] text-ink-faint">
          A retrieval · reranking · adjudication system over DiPiro&apos;s Pharmacotherapy
        </p>
      </div>

      <div className="rule-double mt-7" />
      <div className="rule-hair mt-[3px]" />
    </header>
  );
}

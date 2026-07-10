import { Icon } from './Icon';

/*
  The journal nameplate — front matter at the head of the page. Pared to
  its essentials: the colophon, the grand title, one line of scope, and
  the classic double rule.
*/

export function Nameplate() {
  return (
    <header className="mb-9">
      <div className="flex flex-col items-center text-center">
        <span className="mb-3.5 text-accent">
          <Icon name="aria" size={30} strokeWidth={1.3} />
        </span>
        <h1 className="font-display text-[3rem] font-semibold leading-none tracking-[-0.03em] text-ink sm:text-[4.2rem]">
          ARIA
        </h1>
        <p className="mt-3 font-prose text-[0.95rem] italic text-ink-soft sm:text-[1.02rem]">
          The Journal of Evidence-Grounded Pharmacotherapy
        </p>
      </div>

      <div className="rule-double mt-7" />
      <div className="rule-hair mt-[3px]" />
    </header>
  );
}

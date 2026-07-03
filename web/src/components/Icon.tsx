import type { SVGProps } from 'react';

/*
  One coherent line-icon set, drawn on a 24px grid at 1.6 stroke,
  round caps/joins. Hand-built so the iconography reads as one family —
  no emoji, no mixed icon-pack styles.
*/

export type IconName =
  | 'guardrail'
  | 'navigator'
  | 'generator'
  | 'judge'
  | 'aria'
  | 'send'
  | 'stop'
  | 'sun'
  | 'moon'
  | 'command'
  | 'copy'
  | 'check'
  | 'book'
  | 'close'
  | 'chevron'
  | 'corner'
  | 'caution'
  | 'scope'
  | 'link'
  | 'plus';

const paths: Record<IconName, JSX.Element> = {
  // Agents
  guardrail: <path d="M12 3l7 3v5c0 4.2-2.8 7.5-7 9-4.2-1.5-7-4.8-7-9V6l7-3z" />,
  navigator: (
    <>
      <circle cx="11" cy="11" r="6.5" />
      <path d="M16 16l4 4" />
    </>
  ),
  generator: (
    <>
      <path d="M5 19l9.5-9.5" />
      <path d="M13 5l6 6" />
      <path d="M14.5 3.5l6 6-1.8 1.8-6-6z" />
    </>
  ),
  judge: (
    <>
      <path d="M12 4v15" />
      <path d="M6 19h12" />
      <path d="M5 8h14" />
      <path d="M5 8l-2.5 5a2.5 2.5 0 005 0L5 8z" />
      <path d="M19 8l-2.5 5a2.5 2.5 0 005 0L19 8z" />
    </>
  ),
  // Brand mark — an aperture/iris suggesting focus + retrieval.
  aria: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 3.5L12 12l7.4 4.3" />
      <path d="M12 12L4.6 16.3" />
      <circle cx="12" cy="12" r="2.1" />
    </>
  ),
  send: <path d="M5 12h13M13 6l6 6-6 6" />,
  stop: <rect x="7" y="7" width="10" height="10" rx="1.5" />,
  sun: (
    <>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M2 12h2M20 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4" />
    </>
  ),
  moon: <path d="M20 14.5A8 8 0 019.5 4 8 8 0 1020 14.5z" />,
  command: (
    <path d="M9 6a2 2 0 10-2 2h10a2 2 0 10-2-2v12a2 2 0 102-2H7a2 2 0 102 2V6z" />
  ),
  copy: (
    <>
      <rect x="9" y="9" width="11" height="11" rx="2" />
      <path d="M5 15V6a2 2 0 012-2h9" />
    </>
  ),
  check: <path d="M5 12.5l4 4 10-10" />,
  book: (
    <>
      <path d="M5 5.5A2.5 2.5 0 017.5 3H19v15H7.5A2.5 2.5 0 005 20.5V5.5z" />
      <path d="M5 20.5A2.5 2.5 0 017.5 18H19" />
    </>
  ),
  close: <path d="M6 6l12 12M18 6L6 18" />,
  chevron: <path d="M9 6l6 6-6 6" />,
  corner: <path d="M9 7l-4 4 4 4M5 11h9a4 4 0 014 4v2" />,
  caution: (
    <>
      <path d="M12 4l8.5 15h-17L12 4z" />
      <path d="M12 10v4M12 17h.01" />
    </>
  ),
  scope: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 3.5v17M3.5 12h17" />
    </>
  ),
  link: (
    <>
      <path d="M10 13a3.5 3.5 0 005 0l3-3a3.5 3.5 0 00-5-5l-1.5 1.5" />
      <path d="M14 11a3.5 3.5 0 00-5 0l-3 3a3.5 3.5 0 005 5l1.5-1.5" />
    </>
  ),
  plus: <path d="M12 5v14M5 12h14" />,
};

interface IconProps extends SVGProps<SVGSVGElement> {
  name: IconName;
  size?: number;
}

export function Icon({ name, size = 18, strokeWidth = 1.6, ...rest }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...rest}
    >
      {paths[name]}
    </svg>
  );
}

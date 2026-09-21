/** @type {import('tailwindcss').Config} */

// Colors are driven by CSS variables (see src/styles/tokens.css) using the
// "H S% L%" channel pattern so Tailwind opacity modifiers keep working.
const ch = (v) => `hsl(var(${v}) / <alpha-value>)`;

export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        desk: ch('--desk'),
        page: ch('--page'),
        paper: ch('--paper'),
        rule: ch('--rule'),
        surface: ch('--surface'),
        'surface-raised': ch('--surface-raised'),
        ink: ch('--ink'),
        'ink-soft': ch('--ink-soft'),
        'ink-faint': ch('--ink-faint'),
        line: ch('--line'),
        'line-strong': ch('--line-strong'),
        accent: ch('--accent'),
        'accent-soft': ch('--accent-soft'),
        oxblood: ch('--oxblood'),
        // Evidence tiers
        'tier-strong': ch('--tier-strong'),
        'tier-moderate': ch('--tier-moderate'),
        'tier-limited': ch('--tier-limited'),
      },
      fontFamily: {
        display: ['Fraunces', 'Georgia', 'serif'],
        prose: ['Spectral', 'Georgia', 'serif'],
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'monospace'],
      },
      letterSpacing: {
        label: '0.14em',
        tight2: '-0.018em',
      },
      borderRadius: {
        card: '3px',
        pill: '2px',
      },
      maxWidth: {
        ledger: '46rem',
        prose2: '38rem',
      },
      boxShadow: {
        peek: '0 1px 0 0 hsl(var(--line) / 1), 0 18px 40px -24px hsl(var(--shadow) / 0.55)',
        rail: '0 1px 0 0 hsl(var(--line) / 1)',
      },
      keyframes: {
        'ink-rise': {
          '0%': { opacity: '0', transform: 'translateY(4px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
      animation: {
        'ink-rise': 'ink-rise 0.5s cubic-bezier(0.22, 1, 0.36, 1) both',
      },
    },
  },
  plugins: [],
};

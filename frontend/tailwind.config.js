/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Design tokens from docs/frontend.md
        background: {
          page: 'rgb(var(--bg-page) / <alpha-value>)',
          surface: 'rgb(var(--bg-surface) / <alpha-value>)',
          muted: 'rgb(var(--bg-muted) / <alpha-value>)',
        },
        foreground: {
          primary: 'rgb(var(--fg-primary) / <alpha-value>)',
          secondary: 'rgb(var(--fg-secondary) / <alpha-value>)',
          inverse: 'rgb(var(--fg-inverse) / <alpha-value>)',
        },
        accent: {
          DEFAULT: 'rgb(var(--accent) / <alpha-value>)',
          weak: 'rgb(var(--accent-weak) / <alpha-value>)',
        },
        semantic: {
          success: 'rgb(var(--success) / <alpha-value>)',
          warning: 'rgb(var(--warning) / <alpha-value>)',
          danger: 'rgb(var(--danger) / <alpha-value>)',
        },
        border: 'rgb(var(--border) / <alpha-value>)',
        focus: 'rgb(var(--focus) / <alpha-value>)',
      },
      borderRadius: {
        sm: 'var(--radius-sm)',
        md: 'var(--radius-md)',
        lg: 'var(--radius-lg)',
        pill: 'var(--radius-pill)',
      },
      spacing: {
        // 4px base scale from docs/frontend.md
        '1': 'var(--sp-1)',
        '2': 'var(--sp-2)',
        '3': 'var(--sp-3)',
        '4': 'var(--sp-4)',
        '5': 'var(--sp-5)',
        '6': 'var(--sp-6)',
        '8': 'var(--sp-8)',
        '10': 'var(--sp-10)',
        '12': 'var(--sp-12)',
      },
      boxShadow: {
        sm: 'var(--shadow-sm)',
        md: 'var(--shadow-md)',
        lg: 'var(--shadow-lg)',
      },
      transitionDuration: {
        fast: 'var(--dur-fast)',
        base: 'var(--dur-base)',
        slow: 'var(--dur-slow)',
      },
      transitionTimingFunction: {
        standard: 'var(--ease-standard)',
      },
    },
  },
  plugins: [],
}

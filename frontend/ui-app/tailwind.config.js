/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'monospace'],
        sans: ['Sora', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      colors: {
        surface: '#F5F5F5',
        ink: '#0A0A0A',
        muted: '#888888',
        border: '#E0E0E0',
        page: '#EEEBE5',
        warm: '#F8F6F2',
        accent: {
          blue:   '#0066FF',
          orange: '#FF4400',
          green:  '#00AA44',
          purple: '#7700FF',
          teal:   '#00CCAA',
        },
      },
      backdropBlur: {
        card: '20px',
      },
      animation: {
        'float-slow': 'floatSlow 20s ease-in-out infinite',
        'pulse-orb': 'pulseOrb 300ms ease-in-out',
      },
      keyframes: {
        floatSlow: {
          '0%, 100%': { transform: 'translateY(0px) rotate(0deg)' },
          '33%':      { transform: 'translateY(-20px) rotate(120deg)' },
          '66%':      { transform: 'translateY(10px) rotate(240deg)' },
        },
        pulseOrb: {
          '0%':   { transform: 'scale(1)' },
          '50%':  { transform: 'scale(1.05)' },
          '100%': { transform: 'scale(1)' },
        },
      },
    },
  },
  plugins: [],
}

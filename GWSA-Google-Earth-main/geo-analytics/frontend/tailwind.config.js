/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        gwsa: {
          // Goodwill-aligned light enterprise palette
          bg: '#f7f8fa',
          'bg-alt': '#f3f4f6',
          surface: '#ffffff',
          'surface-hover': '#f5f7fa',
          card: '#ffffff',
          border: '#d7dce2',
          'border-light': '#b8c0ca',
          accent: '#0058a6',
          'accent-hover': '#004783',
          'accent-glow': 'rgba(0, 88, 166, 0.12)',
          'rail-active-bg': 'rgba(0, 88, 166, 0.10)',
          soon: '#f59e0b',
          red: '#ef4444',
          green: '#10b981',
          amber: '#f59e0b',
          cyan: '#06b6d4',
          purple: '#8b5cf6',
          text: '#17212b',
          'text-secondary': '#46515d',
          'text-muted': '#6b7682',
        },
      },
      fontFamily: {
        sans: ['Helvetica Neue', 'Helvetica', 'Arial', 'sans-serif'],
      },
      spacing: {
        rail: '4rem',
        panel: '21.25rem',
      },
      zIndex: {
        rail: '40',
        'rail-panel': '30',
        'side-panel': '20',
        'chat-drawer': '50',
      },
      boxShadow: {
        'glow': '0 0 0 3px rgba(0, 88, 166, 0.12)',
        'glow-lg': '0 0 0 4px rgba(0, 88, 166, 0.14)',
        'card': '0 1px 2px rgba(15, 23, 42, 0.08)',
        'panel': '0 8px 24px rgba(15, 23, 42, 0.14)',
      },
      animation: {
        'slide-in': 'slideIn 0.35s cubic-bezier(0.16, 1, 0.3, 1)',
        'slide-up': 'slideUp 0.35s cubic-bezier(0.16, 1, 0.3, 1)',
        'slide-in-left': 'slideInLeft 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
        'fade-in': 'fadeIn 0.25s ease-out',
        'pulse-soft': 'pulseSoft 2s ease-in-out infinite',
      },
      keyframes: {
        slideIn: { from: { transform: 'translateX(100%)' }, to: { transform: 'translateX(0)' } },
        slideInLeft: {
          from: { transform: 'translateX(-100%)', opacity: '0' },
          to: { transform: 'translateX(0)', opacity: '1' },
        },
        slideUp: { from: { transform: 'translateY(100%)' }, to: { transform: 'translateY(0)' } },
        fadeIn: { from: { opacity: '0' }, to: { opacity: '1' } },
        pulseSoft: { '0%, 100%': { opacity: '1' }, '50%': { opacity: '0.7' } },
      },
    },
  },
  plugins: [require('@tailwindcss/forms')],
};

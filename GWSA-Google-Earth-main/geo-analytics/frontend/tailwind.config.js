/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        gwsa: {
          // Light, neutral, \"enterprise\" palette
          bg: '#f5f5f7',
          'bg-alt': '#edf2f7',
          surface: '#ffffff',
          'surface-hover': '#f1f5f9',
          card: '#ffffff',
          border: '#e2e8f0',
          'border-light': '#cbd5e1',
          accent: '#2563eb',
          'accent-hover': '#1d4ed8',
          'accent-glow': 'rgba(37, 99, 235, 0.12)',
          red: '#ef4444',
          green: '#10b981',
          amber: '#f59e0b',
          cyan: '#06b6d4',
          purple: '#8b5cf6',
          text: '#0f172a',
          'text-secondary': '#475569',
          'text-muted': '#94a3b8',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      },
      boxShadow: {
        'glow': '0 0 20px rgba(59, 130, 246, 0.15)',
        'glow-lg': '0 0 40px rgba(59, 130, 246, 0.2)',
        'card': '0 4px 24px rgba(0, 0, 0, 0.3)',
        'panel': '0 8px 40px rgba(0, 0, 0, 0.5)',
      },
      animation: {
        'slide-in': 'slideIn 0.35s cubic-bezier(0.16, 1, 0.3, 1)',
        'slide-up': 'slideUp 0.35s cubic-bezier(0.16, 1, 0.3, 1)',
        'fade-in': 'fadeIn 0.25s ease-out',
        'pulse-soft': 'pulseSoft 2s ease-in-out infinite',
      },
      keyframes: {
        slideIn: { from: { transform: 'translateX(100%)' }, to: { transform: 'translateX(0)' } },
        slideUp: { from: { transform: 'translateY(100%)' }, to: { transform: 'translateY(0)' } },
        fadeIn: { from: { opacity: '0' }, to: { opacity: '1' } },
        pulseSoft: { '0%, 100%': { opacity: '1' }, '50%': { opacity: '0.7' } },
      },
    },
  },
  plugins: [require('@tailwindcss/forms')],
};

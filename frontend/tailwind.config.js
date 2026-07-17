/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        bg: {
          DEFAULT: '#0A0F1E',
          card: '#0D1526',
          panel: '#111D35',
          hover: '#162040',
        },
        primary: {
          DEFAULT: '#2563EB',
          hover: '#1D4ED8',
          light: '#3B82F6',
          muted: '#1E3A6E',
        },
        accent: {
          green: '#10B981',
          'green-muted': '#064E3B',
          yellow: '#F59E0B',
          'yellow-muted': '#451A03',
          red: '#EF4444',
          'red-muted': '#450A0A',
          purple: '#8B5CF6',
          'purple-muted': '#2E1065',
        },
        border: {
          DEFAULT: '#1E2D4A',
          light: '#243554',
        },
        text: {
          primary: '#F1F5F9',
          secondary: '#94A3B8',
          muted: '#475569',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      backgroundImage: {
        'glass': 'linear-gradient(135deg, rgba(13,21,38,0.8) 0%, rgba(17,29,53,0.6) 100%)',
        'glass-card': 'linear-gradient(135deg, rgba(13,21,38,0.9) 0%, rgba(17,29,53,0.8) 100%)',
        'gradient-primary': 'linear-gradient(135deg, #2563EB 0%, #7C3AED 100%)',
      },
      backdropBlur: {
        xs: '2px',
      },
      animation: {
        'fade-in': 'fadeIn 0.2s ease-out',
        'slide-in': 'slideIn 0.3s ease-out',
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideIn: {
          '0%': { opacity: '0', transform: 'translateY(-8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
      boxShadow: {
        'glass': '0 4px 24px rgba(0,0,0,0.4)',
        'glow': '0 0 20px rgba(37,99,235,0.3)',
        'glow-green': '0 0 20px rgba(16,185,129,0.3)',
      },
    },
  },
  plugins: [],
}

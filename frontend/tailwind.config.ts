import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        dark: {
          bg: '#070a13',
          surface: '#0c111d',
          card: '#0f172a',
          cardMuted: '#141d33',
          border: 'rgba(255, 255, 255, 0.07)',
          borderGlow: 'rgba(56, 189, 248, 0.25)',
        },
        brand: {
          50: '#f0f9ff',
          100: '#e0f2fe',
          400: '#38bdf8',
          500: '#0284c7',
          600: '#0369a1',
          700: '#075985',
          900: '#0c4a6e',
        },
        neon: {
          cyan: '#00f2fe',
          blue: '#3b82f6',
          purple: '#8b5cf6',
          orange: '#ff6b35',
          amber: '#f59e0b',
          emerald: '#10b981',
        },
      },
      boxShadow: {
        'glass': '0 8px 32px 0 rgba(0, 0, 0, 0.45)',
        'neon-blue': '0 0 25px -3px rgba(59, 130, 246, 0.45)',
        'neon-cyan': '0 0 25px -3px rgba(0, 242, 254, 0.45)',
        'neon-purple': '0 0 25px -3px rgba(139, 92, 246, 0.45)',
        'neon-orange': '0 0 25px -3px rgba(255, 107, 53, 0.45)',
        'card-glow': '0 10px 40px -10px rgba(0, 0, 0, 0.6), 0 0 1px 1px rgba(255, 255, 255, 0.05)',
      },
      fontFamily: {
        sans: ['Vazirmatn', 'system-ui', '-apple-system', 'sans-serif'],
      },
      animation: {
        'pulse-slow': 'pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'wave': 'wave 6s ease-in-out infinite alternate',
      },
      keyframes: {
        wave: {
          '0%': { transform: 'translateY(0px)' },
          '100%': { transform: 'translateY(-4px)' },
        },
      },
    },
  },
  plugins: [],
};
export default config;

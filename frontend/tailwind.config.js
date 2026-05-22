/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/app/**/*.{js,ts,jsx,tsx}',
    './src/components/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        // Distinctive serif for display, geometric sans for body, mono for numbers
        display: ['"Fraunces"', 'Georgia', 'serif'],
        sans: ['"Geist"', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
      colors: {
        // Refined dark editorial palette
        ink: {
          DEFAULT: '#0a0a0a',
          50: '#fafaf9',
          100: '#f4f4f3',
          200: '#e7e6e3',
          300: '#d2d0cb',
          400: '#a8a59d',
          500: '#7a766e',
          600: '#5a5751',
          700: '#3d3b37',
          800: '#26241f',
          900: '#0a0a0a',
        },
        accent: {
          // Saffron — single bold accent color
          DEFAULT: '#e8602c',
          50: '#fef3ee',
          100: '#fde0d0',
          400: '#f5895a',
          500: '#e8602c',
          600: '#c8431a',
          700: '#9d3415',
        },
        chart: {
          1: '#e8602c',
          2: '#2d8f7a',
          3: '#d4a72c',
          4: '#5e7ce2',
          5: '#9d3415',
          6: '#7a766e',
        },
      },
      borderRadius: {
        none: '0',
        sm: '2px',
        DEFAULT: '4px',
        md: '6px',
        lg: '8px',
      },
      boxShadow: {
        card: '0 1px 0 rgba(10,10,10,0.04), 0 0 0 1px rgba(10,10,10,0.06)',
        'card-hover': '0 4px 16px rgba(10,10,10,0.06), 0 0 0 1px rgba(10,10,10,0.08)',
      },
      animation: {
        'fade-in': 'fadeIn 0.4s ease-out',
        'slide-up': 'slideUp 0.5s cubic-bezier(0.16, 1, 0.3, 1)',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [],
};

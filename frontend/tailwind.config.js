/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#F5F3FF',
          100: '#EDE9FE',
          200: '#DDD6FE',
          300: '#C4B5FD',
          400: '#A78BFA',
          500: '#8B5CF6',
          600: '#6D4AFF', // Authoritative violet brand
          700: '#5B3FD0', // Authoritative deep violet
          800: '#4C1D95',
          900: '#2E1065',
        },
        sidebar: {
          bg: '#1E1546', // Authoritative dark indigo sidebar
          hover: '#2A1F5E',
          active: '#5B3FD0',
        },
        surface: {
          light: '#F6F5FB', // Authoritative light background
          card: '#FFFFFF',
          darkBg: '#0F0B1E',
          darkCard: '#1A162B',
          darkBorder: '#2E274A',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      },
    },
  },
  plugins: [],
};

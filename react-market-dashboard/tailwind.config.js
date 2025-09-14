/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'dark-bg': '#0B0F14',
        'dark-card': '#121821',
        'dark-border': '#202938',
        'dark-muted': '#94A3B8',
        'dark-text': '#E6EDF3',
        'dark-accent': '#6EA8FE',
        'success': '#22C55E',
        'danger': '#F43F5E',
        'warning': '#F59E0B',
        'info': '#22D3EE',
        'purple': '#A78BFA'
      },
      fontFamily: {
        'sans': ['-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
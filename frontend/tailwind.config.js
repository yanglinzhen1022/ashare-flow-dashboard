/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        stockBg: '#0B0F19',
        panelBg: '#121827',
        stockRed: '#FF4D4F',
        stockGreen: '#22C55E',
      }
    },
  },
  plugins: [],
}

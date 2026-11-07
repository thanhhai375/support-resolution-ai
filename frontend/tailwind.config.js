/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  corePlugins: { preflight: false },
  theme: { extend: { colors: { brand: '#4655ff', workspace: '#f5f6ff', navy: '#151c50' } } },
  plugins: [],
}

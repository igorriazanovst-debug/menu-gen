/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        tomato:    '#E63946',
        avocado:   '#588157',
        lemon:     '#F4A261',
        rice:      '#F1FAEE',
        chocolate: '#1D3557',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      borderRadius: {
        xl: '0.75rem', '2xl': '1rem',
      },
    },
  },
  plugins: [],
};

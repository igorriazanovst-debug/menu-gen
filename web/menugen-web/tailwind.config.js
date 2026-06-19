/** @type {import('tailwindcss').Config} */

// MG_SKIN: цвет из CSS-переменной с поддержкой alpha-модификаторов Tailwind.
const v = (name) => `rgb(var(${name}) / <alpha-value>)`;

module.exports = {
  content: ['./src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // MG_SKIN: семантические токены (управляются скином через data-skin)
        bg:          v('--c-bg'),
        surface:     v('--c-surface'),
        'surface-alt': v('--c-surface-alt'),
        text:        v('--c-text'),
        muted:       v('--c-muted'),
        border:      v('--c-border'),
        primary:     v('--c-primary'),
        'primary-fg': v('--c-primary-fg'),
        secondary:   v('--c-secondary'),
        accent:      v('--c-accent'),
        danger:      v('--c-danger'),
        success:     v('--c-success'),
        warning:     v('--c-warning'),

        // MG_SKIN: legacy-алиасы старого бренда → те же токены,
        // чтобы существующие экраны автоматически реагировали на скин
        // (постепенно мигрируем на семантические имена в Фазе 1).
        tomato:    v('--c-primary'),
        avocado:   v('--c-secondary'),
        lemon:     v('--c-accent'),
        rice:      v('--c-bg'),
        chocolate: v('--c-text'),
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

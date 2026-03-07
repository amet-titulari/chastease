/** @type {import('tailwindcss').Config} */

function withOpacity(variableName) {
  return ({ opacityValue }) => {
    if (opacityValue !== undefined) {
      return `rgba(var(${variableName}), ${opacityValue})`;
    }
    return `rgb(var(${variableName}))`;
  };
}

module.exports = {
  content: [
    './src/chastease/templates/**/*.html',
    './src/chastease/static/js/**/*.js',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: withOpacity('--color-surface'),
          alt: withOpacity('--color-surface-alt'),
          elevated: withOpacity('--color-surface-elevated'),
          input: withOpacity('--color-surface-input'),
        },
        brand: {
          DEFAULT: withOpacity('--color-border'),
          muted: 'var(--color-border-muted)',
        },
        text: {
          DEFAULT: withOpacity('--color-text'),
          secondary: withOpacity('--color-text-secondary'),
          tertiary: withOpacity('--color-text-tertiary'),
        },
        accent: {
          DEFAULT: withOpacity('--color-accent'),
          hover: withOpacity('--color-accent-hover'),
          muted: 'var(--color-accent-muted)',
        },
        danger: {
          DEFAULT: withOpacity('--color-danger'),
          hover: withOpacity('--color-danger-hover'),
        },
        success: {
          DEFAULT: withOpacity('--color-success'),
          hover: withOpacity('--color-success-hover'),
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      borderRadius: {
        card: '0.75rem',
      },
      transitionDuration: {
        DEFAULT: '200ms',
      },
      animation: {
        'fade-in': 'fadeIn 0.3s ease-out',
        'slide-up': 'slideUp 0.3s ease-out',
        'pulse-soft': 'pulseSoft 2s ease-in-out infinite',
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
        pulseSoft: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.6' },
        },
      },
    },
  },
  plugins: [],
};

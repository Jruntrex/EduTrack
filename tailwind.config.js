/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './main/templates/**/*.html',
    './main/static/js/**/*.js',
  ],
  theme: {
    extend: {
      colors: {
        primary: '#5B84FF',
        secondary: '#FF6B6B',
        accent: '#4CAF50',
        error: '#E74C3C',
        dark: '#2F3640',
        bodyText: '#5E6C84',
        neutral: '#A9A9A9',
        tableBorder: 'rgba(0, 0, 0, 0.1)',
        tableBgLight: 'rgba(255, 255, 255, 0.5)',
        tableBgDark: 'rgba(91, 132, 255, 0.05)',
      },
      backgroundImage: {
        'main-gradient': 'linear-gradient(135deg, #D9E0EE 0%, #F3E8EE 100%)',
      },
      backgroundColor: {
        'glass': 'rgba(255, 255, 255, 0.7)',
        'glass-hover': 'rgba(255, 255, 255, 0.9)',
      },
      boxShadow: {
        'glass': '0 8px 32px 0 rgba(0, 0, 0, 0.1)',
        'button': '0 4px 15px rgba(91, 132, 255, 0.3)',
        'button-hover': '0 6px 20px rgba(91, 132, 255, 0.4)',
      },
      backdropBlur: {
        'glass': '8px',
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 'Helvetica Neue', 'sans-serif'],
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(20px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        }
      },
      animation: {
        'fade-in': 'fadeIn 0.5s ease-out forwards',
        'slide-up': 'slideUp 0.5s ease-out forwards',
      }
    },
  },
  plugins: [],
}

/**
 * PostCSS Configuration
 *
 * WHAT: Configures PostCSS plugins for CSS processing.
 *
 * WHY: PostCSS processes our CSS through Tailwind and Autoprefixer,
 * enabling utility-first CSS and automatic vendor prefixing for
 * cross-browser compatibility.
 *
 * HOW: Vite automatically uses this config during development and build.
 */

export default {
  plugins: {
    '@tailwindcss/postcss': {},
  },
}

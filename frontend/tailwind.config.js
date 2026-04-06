/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: "#0D9488",
          hover: "#14B8A6",
          muted: "#ECFEFF",
          foreground: "#042F2E",
        },
        accent: "#0284C7",
        success: { DEFAULT: "#15803D", surface: "#F0FDF4" },
        warning: { DEFAULT: "#B45309", surface: "#FFFBEB" },
        error: { DEFAULT: "#B91C1C", surface: "#FEF2F2" },
        // Flat keys so bg-surface-* utilities resolve under @apply in Vite/PostCSS.
        "surface-page": "#F4F7FB",
        "surface-elevated": "#FFFFFF",
        "surface-subtle": "#EEF2F7",
        border: { DEFAULT: "#E2E8F0", strong: "#CBD5E1" },
        // Flat keys (not ink.DEFAULT) so @apply text-ink / text-ink-muted resolve reliably in Vite/PostCSS.
        ink: "#0F172A",
        "ink-muted": "#64748B",
      },
      fontFamily: {
        sans: [
          '"Plus Jakarta Sans"',
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "sans-serif",
        ],
        mono: [
          '"IBM Plex Mono"',
          "ui-monospace",
          "SF Mono",
          "monospace",
        ],
      },
      boxShadow: {
        shell: "0 1px 3px rgba(15, 23, 42, 0.06), 0 12px 40px rgba(15, 23, 42, 0.06)",
        card: "0 1px 2px rgba(15, 23, 42, 0.04), 0 8px 24px rgba(15, 23, 42, 0.06)",
        glow: "0 0 0 1px rgba(13, 148, 136, 0.12), 0 12px 40px rgba(13, 148, 136, 0.08)",
      },
      backgroundImage: {
        "mesh-page":
          "radial-gradient(ellipse 80% 50% at 50% -20%, rgba(45, 212, 191, 0.15), transparent), radial-gradient(ellipse 60% 40% at 100% 0%, rgba(14, 165, 233, 0.08), transparent), radial-gradient(ellipse 50% 30% at 0% 100%, rgba(99, 102, 241, 0.06), transparent)",
      },
      minHeight: { dropzone: "180px" },
    },
  },
  plugins: [],
};

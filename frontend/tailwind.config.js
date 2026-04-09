/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: "#0D9488",
          hover: "#0F766E",
          muted: "#F0FDFA",
          foreground: "#042F2E",
        },
        accent: "#0284C7",
        success: { DEFAULT: "#15803D", surface: "#F0FDF4" },
        warning: { DEFAULT: "#B45309", surface: "#FFFBEB" },
        error: { DEFAULT: "#B91C1C", surface: "#FEF2F2" },
        "surface-page": "#F5F5F7",
        "surface-elevated": "#FFFFFF",
        "surface-subtle": "#FAFAFA",
        border: { DEFAULT: "rgba(0,0,0,0.08)", strong: "rgba(0,0,0,0.12)" },
        ink: "#1D1D1F",
        "ink-muted": "#6E6E73",
      },
      fontFamily: {
        sans: [
          "system-ui",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Roboto",
          "Helvetica Neue",
          "Arial",
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
        shell: "0 1px 0 rgba(0, 0, 0, 0.04)",
        card: "0 2px 16px rgba(0, 0, 0, 0.06)",
        glow: "0 0 0 1px rgba(0, 0, 0, 0.06)",
      },
      minHeight: { dropzone: "180px" },
    },
  },
  plugins: [],
};

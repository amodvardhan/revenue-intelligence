/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: "#0F766E",
          hover: "#0D9488",
          muted: "#F0FDFA",
        },
        accent: "#0369A1",
        success: { DEFAULT: "#15803D", surface: "#F0FDF4" },
        warning: { DEFAULT: "#B45309", surface: "#FFFBEB" },
        error: { DEFAULT: "#B91C1C", surface: "#FEF2F2" },
        surface: {
          page: "#F8FAFC",
          elevated: "#FFFFFF",
          subtle: "#F1F5F9",
        },
        border: { DEFAULT: "#E2E8F0", strong: "#CBD5E1" },
      },
      fontFamily: {
        sans: [
          "ui-sans-serif",
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
          "SF Mono",
          "ui-monospace",
          "Cascadia Mono",
          "Segoe UI Mono",
          "monospace",
        ],
      },
      minHeight: { dropzone: "160px" },
    },
  },
  plugins: [],
};

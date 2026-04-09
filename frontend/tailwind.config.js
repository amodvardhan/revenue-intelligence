/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: "#0D9488",
          hover: "#0F766E",
          light: "#2DD4BF",
          muted: "#ECFDF5",
          foreground: "#042F2E",
        },
        accent: "#0284C7",
        success: { DEFAULT: "#15803D", surface: "#F0FDF4", muted: "#DCFCE7" },
        warning: { DEFAULT: "#B45309", surface: "#FFFBEB" },
        error: { DEFAULT: "#B91C1C", surface: "#FEF2F2" },
        /* Light canvas */
        "surface-page": "#F0F1F5",
        "surface-elevated": "#FFFFFF",
        "surface-subtle": "#F4F5F8",
        /* Dark chrome (sidebar, auth rail) */
        sidebar: {
          DEFAULT: "#0F1014",
          elevated: "#16181D",
          deep: "#0A0B0E",
          border: "rgba(255,255,255,0.07)",
          label: "#71717A",
          muted: "#A1A1AA",
          ink: "#FAFAFA",
        },
        border: { DEFAULT: "rgba(0,0,0,0.07)", strong: "rgba(0,0,0,0.11)" },
        ink: "#0C0C0E",
        "ink-muted": "#52525B",
        "ink-faint": "#71717A",
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
        card: "0 1px 2px rgba(15, 23, 42, 0.04), 0 12px 32px -8px rgba(15, 23, 42, 0.1)",
        cardHover: "0 2px 4px rgba(15, 23, 42, 0.05), 0 20px 40px -12px rgba(15, 23, 42, 0.12)",
        nav: "4px 0 24px -4px rgba(0, 0, 0, 0.35)",
        glow: "0 0 0 1px rgba(0, 0, 0, 0.06)",
        focus: "0 0 0 3px rgba(13, 148, 136, 0.28)",
      },
      minHeight: { dropzone: "180px" },
      ringOffsetColor: {
        sidebar: "#0F1014",
      },
    },
  },
  plugins: [],
};

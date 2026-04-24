import type { Config } from "tailwindcss";

// Tailwind 将 tokens.css 的 CSS 变量映射为 theme.extend（见特性设计 Key types）
const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        "bg-app": "var(--bg-app)",
        "bg-surface": "var(--bg-surface)",
        "bg-surface-alt": "var(--bg-surface-alt)",
        "bg-hover": "var(--bg-hover)",
        "bg-active": "var(--bg-active)",
        "bg-inset": "var(--bg-inset)",
        fg: "var(--fg)",
        "fg-dim": "var(--fg-dim)",
        "fg-mute": "var(--fg-mute)",
        "fg-faint": "var(--fg-faint)",
        accent: "var(--accent)",
        "accent-hover": "var(--accent-hover)",
        "accent-2": "var(--accent-2)",
        "accent-3": "var(--accent-3)",
        "state-running": "var(--state-running)",
        "state-hil": "var(--state-hil)",
        "state-done": "var(--state-done)",
        "state-fail": "var(--state-fail)",
        "state-retry": "var(--state-retry)",
        "state-pending": "var(--state-pending)",
        "state-classify": "var(--state-classify)",
        border: "var(--border)",
        "border-subtle": "var(--border-subtle)",
        "border-strong": "var(--border-strong)",
      },
      fontFamily: {
        sans: "var(--font-sans)",
        mono: "var(--font-mono)",
      },
      keyframes: {
        "hns-pulse": {
          "0%": { transform: "scale(0.6)", opacity: "0.6" },
          "100%": { transform: "scale(1.8)", opacity: "0" },
        },
      },
      animation: {
        "hns-pulse": "hns-pulse 1.6s cubic-bezier(0.4,0,0.2,1) infinite",
      },
    },
  },
  plugins: [],
};

export default config;

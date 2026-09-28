import type { Config } from "tailwindcss";

export default {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: {
          DEFAULT: "#070b14",
          soft: "#151d33",
          faint: "#5b6478",
        },
        paper: {
          DEFAULT: "#f3f6fb",
          raised: "#ffffff",
        },
        line: {
          DEFAULT: "#e2e8f0",
          soft: "#eef2f8",
        },
        /* Mapped to Aurora accent so existing coral/gold classes update */
        coral: {
          DEFAULT: "#5b54ff",
          deep: "#3d36cc",
          soft: "#eeedff",
          bg: "#f5f4ff",
        },
        gold: {
          DEFAULT: "#5b54ff",
          soft: "#eeedff",
          bg: "#f5f4ff",
        },
        lavender: {
          DEFAULT: "#eeedff",
          deep: "#3d36cc",
          bg: "#f5f4ff",
        },
        teal: {
          DEFAULT: "#059669",
          bg: "#d1fae5",
        },
        brick: {
          DEFAULT: "#e85d4c",
          bg: "#ffe8e4",
        },
        text: {
          DEFAULT: "#070b14",
          muted: "#5b6478",
          faint: "#8b93a7",
        },
        background: "var(--background)",
        foreground: "var(--foreground)",
        card: {
          DEFAULT: "var(--card)",
          foreground: "var(--card-foreground)",
        },
        primary: {
          DEFAULT: "var(--primary)",
          foreground: "var(--primary-foreground)",
          subtle: "var(--primary-subtle)",
        },
        secondary: {
          DEFAULT: "var(--secondary)",
          foreground: "var(--secondary-foreground)",
        },
        muted: {
          DEFAULT: "var(--muted)",
          foreground: "var(--muted-foreground)",
        },
        accent: {
          DEFAULT: "var(--accent)",
          foreground: "var(--accent-foreground)",
          subtle: "var(--accent-subtle)",
        },
        destructive: "var(--destructive)",
        border: "var(--border)",
        input: "var(--input)",
        ring: "var(--ring)",
        sidebar: {
          DEFAULT: "var(--sidebar)",
          foreground: "var(--sidebar-foreground)",
          muted: "var(--sidebar-muted)",
          accent: "var(--sidebar-accent)",
          border: "var(--sidebar-border)",
        },
        "bg-app": "var(--bg-app)",
        "bg-surface": "var(--bg-surface)",
        "bg-elevated": "var(--bg-elevated)",
        "text-primary": "var(--text-primary)",
        "text-secondary": "var(--text-secondary)",
        "text-muted": "var(--text-muted)",
        success: {
          DEFAULT: "var(--success)",
          subtle: "var(--success-subtle)",
        },
        warning: {
          DEFAULT: "var(--warning)",
          subtle: "var(--warning-subtle)",
        },
        error: {
          DEFAULT: "var(--error)",
          subtle: "var(--error-subtle)",
        },
        ai: {
          DEFAULT: "var(--ai)",
          subtle: "var(--ai-subtle)",
        },
        chart: {
          1: "var(--chart-1)",
          2: "var(--chart-2)",
          3: "var(--chart-3)",
          4: "var(--chart-4)",
        },
        ember: {
          DEFAULT: "#e85d4c",
          deep: "#c44738",
          soft: "#ffe8e4",
        },
        mkt: {
          ink: "#070b14",
          muted: "#5b6478",
          canvas: "#f3f6fb",
          "canvas-soft": "#eef2f8",
          indigo: "#5b54ff",
          "indigo-deep": "#3d36cc",
          coral: "#e85d4c",
          hairline: "#e2e8f0",
        },
      },
      borderRadius: {
        sm: "var(--radius-sm)",
        md: "var(--radius-md)",
        lg: "var(--radius-lg)",
        xl: "28px",
        "2xl": "32px",
        "3xl": "40px",
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        serif: ["var(--font-serif)", "Georgia", "serif"],
      },
      boxShadow: {
        sm: "0 2px 8px rgba(7, 11, 20, 0.05)",
        soft: "var(--shadow-soft)",
        card: "var(--shadow-card)",
        glow: "var(--shadow-glow)",
      },
      keyframes: {
        riseIn: {
          from: { opacity: "0", transform: "translateY(10px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        fadeIn: {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        pulseSoft: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.7" },
        },
        shimmer: {
          "0%": { backgroundPosition: "200% 0" },
          "100%": { backgroundPosition: "-200% 0" },
        },
      },
      animation: {
        riseIn: "riseIn 520ms cubic-bezier(0.22, 1, 0.36, 1) both",
        fadeIn: "fadeIn 400ms ease-out both",
        pulseSoft: "pulseSoft 2.4s ease-in-out infinite",
        shimmer: "shimmer 2.2s linear infinite",
      },
    },
  },
  plugins: [],
} satisfies Config;

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
          DEFAULT: "#1e1a24",
          soft: "#2f2936",
          faint: "#4a4352",
        },
        paper: {
          DEFAULT: "#fef7ff",
          raised: "#ffffff",
        },
        line: {
          DEFAULT: "#ebe4f0",
          soft: "#f3eef8",
        },
        coral: {
          DEFAULT: "#d63b20",
          deep: "#b32107",
          soft: "#ffdad3",
          bg: "#fff1ee",
        },
        gold: {
          DEFAULT: "#d63b20",
          soft: "#ffdad3",
          bg: "#fff1ee",
        },
        lavender: {
          DEFAULT: "#e2dfff",
          deep: "#0c006b",
          bg: "#f3eef8",
        },
        teal: {
          DEFAULT: "#047857",
          bg: "#d1fae5",
        },
        brick: {
          DEFAULT: "#b32107",
          bg: "#ffdad3",
        },
        text: {
          DEFAULT: "#1e1a24",
          muted: "#5b403b",
          faint: "#8a7a76",
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
      },
      borderRadius: {
        sm: "var(--radius-sm)",
        md: "var(--radius-md)",
        lg: "var(--radius-lg)",
        xl: "32px",
        "2xl": "40px",
        "3xl": "48px",
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        serif: ["var(--font-serif)", "Georgia", "serif"],
      },
      boxShadow: {
        sm: "0 2px 6px rgba(45, 38, 56, 0.05)",
        soft: "var(--shadow-soft)",
        card: "var(--shadow-card)",
      },
      keyframes: {
        riseIn: {
          from: { opacity: "0", transform: "translateY(6px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        riseIn: "riseIn 480ms cubic-bezier(0.22, 1, 0.36, 1) both",
      },
    },
  },
  plugins: [],
} satisfies Config;

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
          DEFAULT: "#16231F",
          soft: "#223229",
          faint: "#2C4136",
        },
        paper: {
          DEFAULT: "#F1EFE5",
          raised: "#FBFAF4",
        },
        line: {
          DEFAULT: "#DCD9CA",
          soft: "#E7E4D6",
        },
        gold: {
          DEFAULT: "#B9822E",
          soft: "#E6C98A",
          bg: "#F3E6C9",
        },
        teal: {
          DEFAULT: "#2E6B59",
          bg: "#DEEBE4",
        },
        brick: {
          DEFAULT: "#AA4630",
          bg: "#F1DAD1",
        },
        text: {
          DEFAULT: "#1D2620",
          muted: "#63706A",
          faint: "#8B958E",
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
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        serif: ["var(--font-serif)", "Georgia", "serif"],
      },
      boxShadow: {
        sm: "0 1px 2px rgba(0, 0, 0, 0.05)",
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

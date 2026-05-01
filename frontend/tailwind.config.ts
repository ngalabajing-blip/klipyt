import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  darkMode: ["class"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#fffbeb",
          100: "#fef3c7",
          200: "#fde68a",
          300: "#fcd34d",
          400: "#fbbf24",
          500: "#f59e0b",
          600: "#d97706",
          700: "#b45309",
          800: "#92400e",
          900: "#78350f"
        }
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"]
      },
      keyframes: {
        glow: {
          "0%,100%": { opacity: "0.7" },
          "50%": { opacity: "1" }
        }
      },
      animation: {
        glow: "glow 2s ease-in-out infinite"
      }
    }
  },
  plugins: []
};

export default config;

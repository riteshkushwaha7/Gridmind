import type { Config } from "tailwindcss";

/**
 * Design tokens, GRIDMIND v2.
 *
 * Two parallel namespaces:
 *   - `blueprint-*` — legacy semantic names (navy/mist/amber/slate/teal) repainted
 *     to the new palette so existing components inherit the rebrand without
 *     touching their JSX.
 *   - `bm-*` — new names introduced for the v2 design language; reach for
 *     these in new components.
 *
 * Palette inspiration: dark forest navigation + lime-green primary accent +
 * magenta highlight + clean off-white surface in light mode.
 */
const config: Config = {
  darkMode: "class",
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        blueprint: {
          // Dark base, very slight green undertone — used as page bg in dark mode.
          navy: "#0D1614",
          // Clean off-white with a hint of warm green — page bg in light mode.
          mist: "#F4F7F1",
          // PRIMARY brand accent — vibrant lime green.
          amber: "#B5F23A",
          // Quiet secondary — green-grey for icons, muted fills, progress bars.
          slate: "#5C6F66",
          // Status / data viz green (slightly brighter than the old teal).
          teal: "#14B89A",
        },
        // v2 namespace — opt-in for new components.
        bm: {
          ink:       "#0D1614", // page bg, sidebar
          graphite:  "#14201B", // card surface in dark mode
          carbon:    "#1B2823", // raised surface (modals, popovers) dark mode
          line:      "#26352E", // borders / dividers in dark mode
          lime:      "#B5F23A", // primary accent
          "lime-soft": "#D4F77C", // hover / lighter accent
          magenta:   "#FF3D8A", // highlight (progress, play, focus rings)
          coral:     "#FF7A59", // warning-ish secondary
          slate:     "#5C6F66", // muted secondary
          surface:   "#F8FAF5", // card surface in light mode
          mist:      "#F4F7F1", // page bg in light mode
          danger:    "#EF4444", // destructive
          warn:      "#F59E0B", // warning state (separate from brand)
          ok:        "#14B89A", // success state
        },
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      borderRadius: {
        card: "1rem",     // 16px — standard card radius for the new look
        chip: "999px",
      },
      boxShadow: {
        card:  "0 1px 2px rgba(13, 22, 20, 0.04), 0 8px 24px -12px rgba(13, 22, 20, 0.10)",
        glow:  "0 0 0 1px rgba(181, 242, 58, 0.45), 0 8px 28px -8px rgba(181, 242, 58, 0.40)",
      },
      spacing: {
        "18": "4.5rem",
      },
    },
  },
  plugins: [],
};

export default config;

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // "Instrument panel" palette: a cool graphite base (this is an
        // operations tool that watches spend and performance, not a
        // marketing landing page) with a single warm signal color reserved
        // for anything that means "this needs your attention" — a paused
        // campaign, an alert, a pending approval. Everything else stays
        // quiet so the signal color keeps its meaning.
        ink: {
          950: "#0B0E13",
          900: "#12161F",
          800: "#1B212D",
          700: "#262E3D",
          600: "#38445A",
          500: "#54627D",
          400: "#7C89A3",
          300: "#A9B3C7",
          200: "#CDD3E0",
          100: "#E7EAF1",
          50: "#F5F6FA",
        },
        signal: {
          // Reserved exclusively for attention-needed states: paused
          // campaigns, budget alerts, pending approvals. Not used as a
          // generic brand accent — that restraint is what keeps it legible.
          DEFAULT: "#E8722C",
          soft: "#FCE8D9",
        },
        positive: {
          DEFAULT: "#1F8A5F",
          soft: "#DFF3EA",
        },
      },
      fontFamily: {
        // Display/UI face carries structure and hierarchy; mono face is
        // used specifically for anything numeric (spend, ROAS, IDs) so
        // figures read as data, not prose — a small but deliberate nod to
        // the "instrument panel" concept rather than a decorative choice.
        sans: [
          "InterVariable",
          "Inter",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "sans-serif",
        ],
        mono: ["IBM Plex Mono", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      borderRadius: {
        sm: "4px",
        DEFAULT: "6px",
        md: "8px",
        lg: "12px",
      },
      boxShadow: {
        panel: "0 1px 2px 0 rgb(11 14 19 / 0.06), 0 1px 0 0 rgb(11 14 19 / 0.04)",
      },
    },
  },
  plugins: [],
};

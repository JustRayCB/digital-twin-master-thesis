module.exports = {
  content: ["./index.html", "./src/**/*.{ts,svelte}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        desk: "#fdfbf7",
        ink: "#1c1917",
        "cozy-lavender": "#dcd6f7",
        "cozy-peach": "#ffdac1",
        "cozy-mint": "#e2f0cb",
        "cozy-yellow": "#fdfd96",
        "cozy-blue": "#c7cee3",
        "cozy-white": "#ffffff",
        "pop-red": "#ff6961",
      },
      fontFamily: {
        retro: ["'VT323'", "monospace"],
        sans: ["'Space Grotesk'", "sans-serif"],
        handwriting: ["'Indie Flower'", "cursive"],
      },
      boxShadow: {
        hard: "4px 4px 0px 0px #1c1917",
        "hard-sm": "2px 2px 0px 0px #1c1917",
        "hard-lg": "8px 8px 0px 0px #1c1917",
        "hard-xl": "12px 12px 0px 0px #1c1917",
      },
      borderWidth: {
        3: "3px",
      },
      backgroundImage: {
        "grid-pattern": "radial-gradient(#1c1917 1px, transparent 1px)",
      },
      backgroundSize: {
        "grid-sm": "20px 20px",
      },
      animation: {
        "bounce-slow": "bounce 3s infinite",
        wobble: "wobble 1s ease-in-out infinite",
      },
      keyframes: {
        wobble: {
          "0%, 100%": { transform: "rotate(-3deg)" },
          "50%": { transform: "rotate(3deg)" },
        },
      },
    },
  },
  plugins: [require("@tailwindcss/forms"), require("@tailwindcss/container-queries")],
};

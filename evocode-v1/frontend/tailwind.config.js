/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      keyframes: {
        "slide-in": {
          "0%":   { opacity: "0", transform: "translateY(-12px) scale(0.96)" },
          "100%": { opacity: "1", transform: "translateY(0) scale(1)" },
        },
      },
      animation: {
        "slide-in": "slide-in 0.4s ease-out forwards",
      },
    },
  },
  plugins: [],
}

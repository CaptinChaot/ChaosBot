module.exports = {
  content: ["./web/**/*.html"],
  theme: {
    extend: {
      colors: {
        chaosRed: '#ff1a1a',
        chaosDark: '#050505',
        chaosPanel: '#090909',
      },
      boxShadow: {
        glow: '0 0 26px rgba(255, 26, 26, 0.62)',
        glowSoft: '0 0 14px rgba(255, 26, 26, 0.42)',
        glowPurple: '0 0 26px rgba(168, 85, 247, 0.4)',
      }
    }
  }
}
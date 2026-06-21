import { defineConfig, loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  return {
    define: {
      __VWORLD_KEY__: JSON.stringify(env.VITE_VWORLD_KEY || ''),
    },
    build: {
      outDir: 'dist',
      assetsDir: 'assets',
    },
    base: './',
  }
})

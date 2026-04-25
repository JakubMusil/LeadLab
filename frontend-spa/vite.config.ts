import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    vueDevTools(),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    },
  },
  // Output to Django's static directory so collectstatic picks up the SPA assets.
  base: '/static/frontend/spa/',
  build: {
    outDir: '../frontend/static/frontend/spa',
    emptyOutDir: true,
    manifest: true,
  },
})

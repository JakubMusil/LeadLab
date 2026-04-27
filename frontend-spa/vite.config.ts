import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'
import { VitePWA } from 'vite-plugin-pwa'
import VueI18nPlugin from '@intlify/unplugin-vue-i18n/vite'
import { resolve } from 'node:path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    vueDevTools(),
    VueI18nPlugin({
      // Pre-compile all locale JSON files so the runtime-only vue-i18n build
      // is used and no new Function() calls occur at runtime (CSP compliance).
      include: resolve(__dirname, './src/locales/**/*.json'),
    }),
    VitePWA({
      registerType: 'autoUpdate',
      injectRegister: 'auto',
      manifest: false, // we provide our own public/manifest.json
      workbox: {
        // Cache the app shell and all static assets
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'],
        navigateFallback: '/app/',
        navigateFallbackDenylist: [/^\/api\//, /^\/admin\//, /^\/static\//, /^\/media\//],
        runtimeCaching: [
          {
            urlPattern: /^\/api\/v1\//,
            handler: 'NetworkFirst',
            options: {
              cacheName: 'api-cache',
              expiration: { maxEntries: 100, maxAgeSeconds: 60 * 5 },
            },
          },
        ],
      },
    }),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      // Use the runtime-only build of vue-i18n so that no message compiler
      // (which calls new Function()) is included — required for CSP compliance.
      'vue-i18n': 'vue-i18n/dist/vue-i18n.runtime.esm-bundler.js',
      // frappe-gantt@1.2.2 only exports its CSS via the root "." entry with a
      // "style" condition; the subpath "./dist/frappe-gantt.css" is absent from
      // the package exports field.  Vite 8 enforces exports strictly in
      // production, so map the import directly to the file to bypass the check.
      'frappe-gantt/dist/frappe-gantt.css': fileURLToPath(
        new URL('./node_modules/frappe-gantt/dist/frappe-gantt.css', import.meta.url),
      ),
    },
  },
  // Output to Django's static directory so collectstatic picks up the SPA assets.
  base: '/static/frontend/spa/',
  build: {
    outDir: '../frontend/static/frontend/spa',
    emptyOutDir: true,
    manifest: true,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('@fullcalendar')) return 'fullcalendar'
          if (id.includes('chart.js') || id.includes('vue-chartjs')) return 'chartjs'
          if (id.includes('node_modules')) return 'vendor'
        },
      },
    },
  },
})

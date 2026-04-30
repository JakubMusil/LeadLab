import { fileURLToPath } from 'node:url'
import { mergeConfig, defineConfig, configDefaults } from 'vitest/config'
import viteConfig from './vite.config'

export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      environment: 'jsdom',
      // Only treat .ts(x) files as specs. The repo also contains
      // tsc-compiled `.spec.js` siblings (build artifacts that ended up
      // tracked); running them double-counts every test and yields
      // duplicate failures. Source-of-truth is the TypeScript spec.
      include: ['src/**/*.{test,spec}.{ts,tsx}'],
      exclude: [...configDefaults.exclude, 'e2e/**'],
      root: fileURLToPath(new URL('./', import.meta.url)),
      setupFiles: ['./src/test/setup.ts'],
    },
  }),
)

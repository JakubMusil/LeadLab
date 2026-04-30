/**
 * Vitest global setup.
 *
 * Registers a vue-i18n instance as a global plugin for `@vue/test-utils`,
 * so any component that calls `useI18n()` in its setup() works in tests
 * without needing per-spec mocks. Locale JSON files are pre-compiled by
 * `@intlify/unplugin-vue-i18n/vite` (inherited from `vite.config.ts`),
 * so the runtime-only vue-i18n build can read them directly.
 */
import { config } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import en from '@/locales/en.json'
import cs from '@/locales/cs.json'
import de from '@/locales/de.json'
import pl from '@/locales/pl.json'

const i18n = createI18n({
  legacy: false,
  locale: 'en',
  fallbackLocale: 'en',
  messages: { en, cs, de, pl },
  // Tests don't render in production-warning mode; silence missing-key
  // noise so an incomplete translation in one locale doesn't drown the
  // real assertions in console output.
  missingWarn: false,
  fallbackWarn: false,
})

config.global.plugins = [...(config.global.plugins ?? []), i18n]

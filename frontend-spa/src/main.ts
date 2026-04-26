import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import App from './App.vue'
import router from './router'
import './assets/main.css'
import en from './locales/en.json'
import cs from './locales/cs.json'
import de from './locales/de.json'
import pl from './locales/pl.json'
import { detectLocale } from './composables/useI18n'
import { pluginRegistry } from './plugins'

// Load first-party plugins (side-effect imports register them via registerPlugin())
import './plugins/slackNotifications'
import './plugins/linkedinEnrichment'
import './plugins/voip'
import './plugins/emailSequences'

const i18n = createI18n({
  legacy: false,
  locale: detectLocale(),
  fallbackLocale: 'en',
  messages: { en, cs, de, pl },
})

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(i18n)
pluginRegistry.forEach((plugin) => plugin.install(app))
app.mount('#app')

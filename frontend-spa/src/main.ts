import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import App from './App.vue'
import router from './router'
import './assets/main.css'
import en from './locales/en.json'
import cs from './locales/cs.json'
import { detectLocale } from './composables/useI18n'
import { pluginRegistry } from './plugins'

const i18n = createI18n({
  legacy: false,
  locale: detectLocale(),
  fallbackLocale: 'en',
  messages: { en, cs },
})

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(i18n)
pluginRegistry.forEach((plugin) => plugin.install(app))
app.mount('#app')

export { useI18n } from 'vue-i18n'

export function setLocale(lang: string): void {
  localStorage.setItem('leadlab-locale', lang)
  window.location.reload()
}

export function detectLocale(): string {
  const stored = localStorage.getItem('leadlab-locale')
  if (stored) return stored
  const browser = navigator.language?.split('-')[0] ?? 'en'
  return ['en', 'cs'].includes(browser) ? browser : 'en'
}

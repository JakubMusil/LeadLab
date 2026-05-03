import { computed } from 'vue'
import { useFirmStore } from '@/stores/firm'
import { useI18n } from '@/composables/useI18n'

// ---------------------------------------------------------------------------
// Supported currencies
// ---------------------------------------------------------------------------

export interface CurrencyOption {
  code: string
  names: Record<string, string>
  defaultLocale: string
}

export const SUPPORTED_CURRENCIES: CurrencyOption[] = [
  { code: 'CZK', names: { cs: 'Česká koruna', en: 'Czech Koruna', de: 'Tschechische Krone', pl: 'Korona czeska' }, defaultLocale: 'cs-CZ' },
  { code: 'EUR', names: { cs: 'Euro', en: 'Euro', de: 'Euro', pl: 'Euro' }, defaultLocale: 'de-DE' },
  { code: 'USD', names: { cs: 'Americký dolar', en: 'US Dollar', de: 'US-Dollar', pl: 'Dolar amerykański' }, defaultLocale: 'en-US' },
  { code: 'GBP', names: { cs: 'Britská libra', en: 'British Pound', de: 'Britisches Pfund', pl: 'Funt brytyjski' }, defaultLocale: 'en-GB' },
  { code: 'PLN', names: { cs: 'Polský zlotý', en: 'Polish Zloty', de: 'Polnischer Złoty', pl: 'Złoty polski' }, defaultLocale: 'pl-PL' },
  { code: 'HUF', names: { cs: 'Maďarský forint', en: 'Hungarian Forint', de: 'Ungarischer Forint', pl: 'Forint węgierski' }, defaultLocale: 'hu-HU' },
  { code: 'CHF', names: { cs: 'Švýcarský frank', en: 'Swiss Franc', de: 'Schweizer Franken', pl: 'Frank szwajcarski' }, defaultLocale: 'de-CH' },
  { code: 'NOK', names: { cs: 'Norská koruna', en: 'Norwegian Krone', de: 'Norwegische Krone', pl: 'Korona norweska' }, defaultLocale: 'nb-NO' },
  { code: 'SEK', names: { cs: 'Švédská koruna', en: 'Swedish Krone', de: 'Schwedische Krone', pl: 'Korona szwedzka' }, defaultLocale: 'sv-SE' },
  { code: 'DKK', names: { cs: 'Dánská koruna', en: 'Danish Krone', de: 'Dänische Krone', pl: 'Korona duńska' }, defaultLocale: 'da-DK' },
  { code: 'RON', names: { cs: 'Rumunský leu', en: 'Romanian Leu', de: 'Rumänischer Leu', pl: 'Lej rumuński' }, defaultLocale: 'ro-RO' },
  { code: 'BGN', names: { cs: 'Bulharský lev', en: 'Bulgarian Lev', de: 'Bulgarischer Lew', pl: 'Lew bułgarski' }, defaultLocale: 'bg-BG' },
  { code: 'UAH', names: { cs: 'Ukrajinská hřivna', en: 'Ukrainian Hryvnia', de: 'Ukrainische Hrywnja', pl: 'Hrywna ukraińska' }, defaultLocale: 'uk-UA' },
  { code: 'RSD', names: { cs: 'Srbský dinár', en: 'Serbian Dinar', de: 'Serbischer Dinar', pl: 'Dinar serbski' }, defaultLocale: 'sr-RS' },
]

export const CURRENCY_DEFAULT_LOCALE: Record<string, string> = {
  CZK: 'cs-CZ',
  EUR: 'de-DE',
  USD: 'en-US',
  GBP: 'en-GB',
  PLN: 'pl-PL',
  HUF: 'hu-HU',
  CHF: 'de-CH',
  NOK: 'nb-NO',
  SEK: 'sv-SE',
  DKK: 'da-DK',
  RON: 'ro-RO',
  BGN: 'bg-BG',
  UAH: 'uk-UA',
  RSD: 'sr-RS',
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

// ---------------------------------------------------------------------------
// Composable
// ---------------------------------------------------------------------------

export function useMoney() {
  const firmStore = useFirmStore()
  const { locale: uiLocale } = useI18n()

  /** ISO 4217 code for the workspace reporting currency (fallback: CZK) */
  const firmCurrency = computed(() => firmStore.activeFirm?.default_currency ?? 'CZK')

  /** BCP 47 locale tag for number/currency formatting (fallback: cs-CZ) */
  const firmLocale = computed(() => firmStore.activeFirm?.number_locale ?? 'cs-CZ')

  /**
   * Format a number as a full currency string using the workspace locale.
   * e.g. 12500.5 → "12 500,50 Kč" (cs-CZ / CZK)
   */
  function formatAmount(n: number | string, currency = firmCurrency.value): string {
    return new Intl.NumberFormat(firmLocale.value, {
      style: 'currency',
      currency,
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(Number(n))
  }

  /**
   * Format a number without currency symbol, only localized separators.
   * e.g. 12500.5 → "12 500,50" (cs-CZ)
   */
  function formatAmountPlain(n: number | string): string {
    return new Intl.NumberFormat(firmLocale.value, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(Number(n))
  }

  /**
   * Parse a locale-formatted string to a JS number.
   * "12 500,50" → 12500.5 (cs-CZ)
   * "12,500.50" → 12500.5 (en-US)
   */
  function parseMoney(s: string): number {
    const parts = new Intl.NumberFormat(firmLocale.value).formatToParts(1111.1)
    const decimal = parts.find((p) => p.type === 'decimal')?.value ?? '.'
    const clean = s
      .replace(new RegExp(`[^0-9${escapeRegex(decimal)}\\-]`, 'g'), '')
      .replace(decimal, '.')
    return parseFloat(clean) || 0
  }

  /** Sorted list of supported currencies with translated labels for the current UI locale. */
  const currencies = computed(() =>
    SUPPORTED_CURRENCIES.map((c) => ({
      code: c.code,
      label: `${c.code} – ${c.names[uiLocale.value] ?? c.names['en']}`,
    })).sort((a, b) => a.label.localeCompare(b.label))
  )

  return { firmCurrency, firmLocale, formatAmount, formatAmountPlain, parseMoney, currencies }
}

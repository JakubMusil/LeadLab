# Money System Goals – LeadLab Currency & Amount Module

## Analýza současného stavu (as-is)

### Problémy v současném kódu

1. **Hardcoded výchozí hodnota CZK** – na desítkách míst v backendu (`default="CZK"`) i frontendu (`ref('CZK')`) je měna zapsána natvrdo.
2. **Fragmentovaný výběr měny** – každý formulář si drží vlastní `ref` pro měnu (LeadsView, ProposalsView, ReportsView, StreamlineCreateModal), bez sdíleného zdroje pravdy.
3. **Nekonzistentní formátování** – různé pohledy používají různé způsoby zobrazení: `Number(n).toFixed(2)`, `toLocaleString()`, `Intl.NumberFormat(undefined, ...)`, holý string concat `${value} ${currency}`. Žádná sdílená utilita.
4. **Chybějící lokalizace číslic** – oddělování tisíců (tečka vs. čárka), desetinný oddělovač (čárka vs. tečka) závisí na nahodilém `undefined` locale nebo není řešeno vůbec.
5. **Statistiky bez jednotné měny** – `pipeline_value`, `won_value`, `total_revenues`, `profit_loss` v API agregují hodnoty napříč libovolnými měnami bez konverze, výsledek je statisticky nesmyslný.
6. **Firm model bez currency** – model `Firm` nemá žádné pole pro výchozí měnu ani locale workspace.
7. **Uživatel musí ručně psát kód měny** – v LeadsView je `<input type="text" maxlength="3" placeholder="CZK">`, což je UX anti-pattern.

---

## Cílový stav (to-be)

Systém měn bude tvořen třemi vzájemně provázanými vrstvami:

```
┌─────────────────────────────────────────────────────────────────────┐
│  1. Workspace default currency  (Firm model + Owner nastavení)     │
│  2. Per-record currency         (Lead, Proposal, Expense, Revenue) │
│  3. useMoney composable         (formátování + vstup, frontend)    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Fáze 1 – Backend: Workspace výchozí měna

### 1.1 Rozšíření modelu `Firm`

Přidat dvě pole do `firms/models.py`:

```
default_currency   CharField(max_length=3, default="CZK")
number_locale      CharField(max_length=10, default="cs-CZ")
                   # BCP 47 locale tag, použit pro Intl.NumberFormat na frontendu
```

- `default_currency` – ISO 4217 třímístný kód (CZK, EUR, USD, GBP, PLN, …).
- `number_locale` – ovlivňuje formátování čísel (oddělovač tisíců, des. tečka/čárka, pozice symbolu).
- Výchozí `"CZK"` / `"cs-CZ"` zajistí zpětnou kompatibilitu bez migrace dat.
- Přidat Django migraci.

### 1.2 Serializace do API `/api/v1/firms/`

Přidat `default_currency` a `number_locale` do `FirmOut` schématu (Ninja schema nebo serializer) a do PATCH endpointu pro nastavení firmy.

### 1.3 Odstranění `default="CZK"` z ostatních modelů

Pole `currency` na modelech `Lead`, `Proposal`, `Expense`, `Revenue` si ponechají svou vlastní hodnotu, ale při vytvoření záznamu bez explicitní měny se použije `firm.default_currency` místo hardcoded `"CZK"`. Toto se řeší na úrovni API handleru (Django Ninja / serializer `create`), nikoliv na úrovni modelu – DB default zůstane `"CZK"` kvůli starším záznamům.

### 1.4 Statistické agregace s ohledem na měnu

Agregační endpointy (`/api/v1/dashboard/stats`, `/api/v1/reports/summary`, …) nyní sčítají hodnoty napříč různými měnami. Navrhované řešení ve dvou krocích:

**Krok A – okamžitý fix (filtr):**  
Agregovat pouze záznamy, jejichž `currency` odpovídá `firm.default_currency`. Ostatní záznamy vyloučit z numerických součtů a doplnit informativní příznak `mixed_currencies: true` v odpovědi.

**Krok B – plný fix (konverze):**  
Přidat volitelné `canonical_amount` a `canonical_currency` pole na modely `Lead`, `Expense`, `Revenue`, `Proposal`. Při uložení záznamu (signal/override `save()`) doplnit přepočítanou hodnotu v `firm.default_currency` pomocí kurzu z vybrané služby (viz Fáze 4). Statistické endpointy pak budou agregovat `canonical_amount`.

---

## Fáze 2 – Frontend: `useMoney` composable

Vytvořit soubor `frontend-spa/src/composables/useMoney.ts`.

### 2.1 API composable

```typescript
useMoney(options?: { currency?: Ref<string> | string })
```

Vrací:

| Název | Typ | Popis |
|---|---|---|
| `formatAmount(n, currency?)` | `(n: number\|string, currency?: string) => string` | Lokalizovaný výstup s měnou, např. „12 500,00 Kč" nebo „€ 12,500.00" |
| `formatAmountPlain(n)` | `(n: number\|string) => string` | Pouze číslo bez symbolu, pro tabulkové sloupce |
| `parseMoney(s)` | `(s: string) => number` | Parsování lokalizovaného vstupu na číslo |
| `currencies` | `ComputedRef<CurrencyOption[]>` | Seřazený seznam dostupných měn |
| `firmCurrency` | `ComputedRef<string>` | Výchozí měna aktivní firmy |
| `firmLocale` | `ComputedRef<string>` | Locale aktivní firmy (pro Intl) |

Interně využívá:
- `useFirmStore()` pro `activeFirm.default_currency` a `activeFirm.number_locale`
- `Intl.NumberFormat` pro formátování a `Intl.NumberFormat.prototype.formatToParts` pro parsing

### 2.2 `CurrencySelect` komponenta

Vytvořit `frontend-spa/src/components/CurrencySelect.vue`.

- Jednoduchý `<select>` (nebo searchable combobox) s předvoleným seznamem měn.
- Zobrazuje kód + název v aktuálním locale (CS: „CZK – Česká koruna", EN: „CZK – Czech Koruna").
- Prop `modelValue: string`, emit `update:modelValue`.
- Výchozí hodnota z `useMoney().firmCurrency` – žádný hardcoded string.
- Tento komponent nahradí všechny `<input type="text" placeholder="CZK">` i `<option>CZK</option>` fragmenty.

### 2.3 `MoneyInput` komponenta

Vytvořit `frontend-spa/src/components/MoneyInput.vue`.

- Input pro zadávání peněžních částek.
- Props: `modelValue: number | null`, `currency: string`, `locale?: string`.
- Zobrazí lokalizovaný formát (např. „12 500,00") při blur, editovatelný čistý číslo-string při focus.
- Validuje vstup a odmítá nečíselné znaky.
- Volitelně zobrazuje symbol měny jako suffix/prefix.
- Interně používá `parseMoney` z `useMoney`.

### 2.4 Refaktoring existujících pohledů

Postupná náhrada v těchto souborech (každý soubor = samostatný úkol/PR):

| Soubor | Co změnit |
|---|---|
| `LeadsView.vue` | `ref('CZK')` → `useMoney().firmCurrency`; `<input type="text">` → `<CurrencySelect>`; `Intl.NumberFormat(undefined…)` → `formatAmount` |
| `ProposalsView.vue` | `ref('CZK')` → `firmCurrency`; `<option>CZK` atd. → `<CurrencySelect>` |
| `ProposalBuilderView.vue` | `fmt()` → `formatAmountPlain`; `CURRENCIES` const → `currencies` z composable; `ref('CZK')` → `firmCurrency` |
| `StreamlineCreateModal.vue` | totéž jako ProposalsView |
| `ReportsView.vue` | `formatMoney` → `formatAmount`; `ref({currency: 'CZK'})` → `firmCurrency` |
| `PublicProposalView.vue` | `fmt()` → `formatAmountPlain`; `{{ proposal.currency }}` suffix → integrovaný do `formatAmount` |
| `CustomerDetailView.vue` | `.toFixed(2)` → `formatAmountPlain` |
| `DashboardView.vue` | `Intl.NumberFormat(undefined…)` → `formatAmount` |

---

## Fáze 3 – Nastavení workspace (Owner UI)

### 3.1 Stránka nastavení firmy

V sekci nastavení firmy (Owner/Admin) přidat panel „Měny a čísla":

- **Výchozí měna workspace** – `<CurrencySelect>` s uložením do `PATCH /api/v1/firms/{id}/`.
- **Formát čísel** – výběr locale (přednastaven dle výchozí měny, možno přepsat):  
  Příklady: `cs-CZ` → „12 500,50 Kč", `de-DE` → „12.500,50 €", `en-US` → „$12,500.50"
- Změna výchozí měny **nezmění** existující záznamy – platí pouze pro nově vytvořené záznamy.

### 3.2 Propagace do frontendu

`FirmOut` schéma rozšířit o `default_currency` a `number_locale`. Tyto hodnoty jsou dostupné přes `useFirmStore().activeFirm`, `useMoney()` je konzumuje automaticky.

---

## Fáze 4 – Volitelná konverze kurzů (budoucí rozšíření)

> Tato fáze není nutná pro MVP, ale je třeba ji architektonicky připravit.

### 4.1 Zdroj kurzů

Možnosti (v pořadí doporučení):
1. **ECB (Evropská centrální banka)** – zdarma, XML feed, aktualizace denně, pokrývá EU měny.
2. **exchangeratesapi.io** – komerční, REST API, easy integration.
3. **fixer.io** – alternativa k výše uvedenému.

### 4.2 Model `ExchangeRate`

```
ExchangeRate:
  base_currency   CharField(3)   # vždy "EUR" (ECB standard)
  quote_currency  CharField(3)
  rate            DecimalField(14, 6)
  date            DateField
  source          CharField(32)  # "ecb" / "manual"
```

Celery beat task stahující kurzy 1× denně.

### 4.3 Přepočet při uložení

`Lead.save()` / signal `post_save` doplní `canonical_amount = convert(value, currency → firm.default_currency, date=today)`.

### 4.4 API helper

```python
# crm/money.py
def to_canonical(amount: Decimal, from_currency: str, to_currency: str, date=None) -> Decimal
```

Použitelný v API i migračních skriptech.

---

## Fáze 5 – Datová migrace existujících záznamů

Po nasazení Fáze 1:

1. Management command `python manage.py backfill_firm_currency` – pro každou firmu nastaví `default_currency` dle nejčastěji používané měny v jejích Leadech.
2. Management command `python manage.py backfill_canonical_amounts` – přepočítá `canonical_amount` na základě historického kurzu (nebo 1:1 pokud je měna shodná s default).

---

## Podporované měny (výchozí seznam)

| Kód | Název CS | Název EN |
|-----|----------|----------|
| CZK | Česká koruna | Czech Koruna |
| EUR | Euro | Euro |
| USD | Americký dolar | US Dollar |
| GBP | Britská libra | British Pound |
| PLN | Polský zlotý | Polish Zloty |
| HUF | Maďarský forint | Hungarian Forint |
| CHF | Švýcarský frank | Swiss Franc |
| NOK | Norská koruna | Norwegian Krone |
| SEK | Švédská koruna | Swedish Krone |
| DKK | Dánská koruna | Danish Krone |
| RON | Rumunský leu | Romanian Leu |
| BGN | Bulharský lev | Bulgarian Lev |

Seznam je uložen jako konstanta v `useMoney.ts` a v Django settings `SUPPORTED_CURRENCIES`. Lze rozšířit.

---

## Lokalizace formátování čísel

| Locale | Příklad částky | Poznámka |
|--------|----------------|----------|
| `cs-CZ` | 12 500,50 Kč | symbol za číslem, mezera jako separator |
| `de-DE` | 12.500,50 € | tečka tisíce, čárka des. |
| `en-US` | $12,500.50 | symbol před číslem, čárka tisíce |
| `pl-PL` | 12 500,50 zł | podobně jako cs-CZ |

Veškeré formátování řeší `Intl.NumberFormat` s parametry `{ style: 'currency', currency, locale }` z `firm.number_locale`. Žádné ruční formátování v komponentách.

---

## Architektura `useMoney.ts` (sketch)

```typescript
// frontend-spa/src/composables/useMoney.ts

export interface CurrencyOption {
  code: string   // 'CZK'
  labelCs: string
  labelEn: string
  // ...
}

export const SUPPORTED_CURRENCIES: CurrencyOption[] = [ /* ... */ ]

export function useMoney() {
  const firmStore = useFirmStore()

  const firmCurrency = computed(() =>
    firmStore.activeFirm?.default_currency ?? 'CZK'
  )
  const firmLocale = computed(() =>
    firmStore.activeFirm?.number_locale ?? 'cs-CZ'
  )

  function formatAmount(n: number | string, currency = firmCurrency.value): string {
    return new Intl.NumberFormat(firmLocale.value, {
      style: 'currency',
      currency,
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(Number(n))
  }

  function formatAmountPlain(n: number | string): string {
    return new Intl.NumberFormat(firmLocale.value, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(Number(n))
  }

  function parseMoney(s: string): number {
    // Strip non-numeric except decimal separator
    const locale = firmLocale.value
    const parts = new Intl.NumberFormat(locale).formatToParts(1111.1)
    const group = parts.find(p => p.type === 'group')?.value ?? ','
    const decimal = parts.find(p => p.type === 'decimal')?.value ?? '.'
    const clean = s
      .replace(new RegExp(`[^0-9${escapeRegex(decimal)}-]`, 'g'), '')
      .replace(decimal, '.')
    return parseFloat(clean) || 0
  }

  const currencies = computed(() => SUPPORTED_CURRENCIES)

  return { firmCurrency, firmLocale, formatAmount, formatAmountPlain, parseMoney, currencies }
}
```

---

## Prioritizovaný seznam úkolů (backlog)

### P0 – Kritické (blocker pro statistiky)
- [ ] Přidat `default_currency` + `number_locale` do modelu `Firm` + migrace
- [ ] Rozšířit `FirmOut` a PATCH endpoint
- [ ] Opravit dashboard stats a reports summary – agregovat pouze záznamy shodné měny, vrátit `mixed_currencies`
- [ ] Backfill management command pro existující firmy

### P1 – Vysoká priorita (UX)
- [ ] Vytvořit `useMoney.ts` composable
- [ ] Vytvořit `CurrencySelect.vue` komponent
- [ ] Vytvořit `MoneyInput.vue` komponent
- [ ] Refaktorovat `LeadsView.vue`
- [ ] Refaktorovat `ProposalsView.vue` a `ProposalBuilderView.vue`
- [ ] Přidat nastavení měny do Owner/Admin settings UI

### P2 – Střední priorita (konzistence)
- [ ] Refaktorovat `ReportsView.vue`, `StreamlineCreateModal.vue`
- [ ] Refaktorovat `PublicProposalView.vue`, `CustomerDetailView.vue`, `DashboardView.vue`
- [ ] Přidat i18n klíče pro názvy měn do `cs.json`, `en.json`, `de.json`, `pl.json`

### P3 – Budoucí rozšíření
- [ ] Model `ExchangeRate` + Celery beat task (ECB feed)
- [ ] `canonical_amount` pole na Lead, Expense, Revenue
- [ ] Backfill canonical amounts s historickými kurzy
- [ ] Rozšíření seznamu podporovaných měn

---

## Závislosti a rizika

| Riziko | Dopad | Mitigace |
|--------|-------|----------|
| Statistiky sčítají různé měny | Statisticky nesprávné hodnoty | P0: filtr na `firm.default_currency` |
| Existující záznamy bez `canonical_amount` | Chybné historické reporty | Backfill command s 1:1 konverzí pro shodné měny |
| `Intl.NumberFormat` parse je nestandardní | Chybný parsing vstupu | Testovat `parseMoney` pro cs-CZ, en-US, de-DE; fallback na `parseFloat` |
| Breaking change `FirmOut` API | Frontend crash | Přidat pole jako optional s default hodnotami |
| Owner změní default_currency | Stávající záznamy mají jinou měnu | Jasná UI notifikace; záznamy zachovat původní měnu |

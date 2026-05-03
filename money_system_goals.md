# Money System Goals – LeadLab Currency & Amount Module

## Analýza současného stavu (as-is)

### Problémy v současném kódu

1. **Hardcoded výchozí hodnota CZK** – na desítkách míst v backendu (`default="CZK"`) i frontendu (`ref('CZK')`) je měna zapsána natvrdo bez možnosti konfigurace.
2. **Fragmentovaný výběr měny** – každý formulář si drží vlastní lokální `ref` pro měnu (LeadsView, ProposalsView, ReportsView, StreamlineCreateModal), bez sdíleného zdroje pravdy. Změna výchozí měny vyžaduje zásah do každého souboru zvlášť.
3. **Nekonzistentní formátování** – různé pohledy používají různé způsoby zobrazení: `Number(n).toFixed(2)`, `toLocaleString()`, `Intl.NumberFormat(undefined, ...)`, holý string concat `${value} ${currency}`. Žádná sdílená utilita, žádný jednotný styl.
4. **Chybějící lokalizace číslic** – oddělování tisíců (tečka vs. čárka), desetinný oddělovač (čárka vs. tečka) závisí na nahodilém `undefined` locale nebo není řešeno vůbec. Česky psaný uživatel vidí `12500.00 CZK` místo `12 500,00 Kč`.
5. **Statistiky bez jednotné měny** – `pipeline_value`, `won_value`, `total_revenues`, `profit_loss` v API agregují hodnoty napříč libovolnými měnami bez konverze; výsledek je statisticky nesmyslný (CZK + EUR + USD = ???).
6. **Firm model bez currency** – model `Firm` nemá žádné pole pro výchozí měnu ani locale workspace. Každý tenant je nucen pracovat s CZK bez možnosti přizpůsobení.
7. **Uživatel musí ručně psát kód měny** – v LeadsView je `<input type="text" maxlength="3" placeholder="CZK">`, což je UX anti-pattern; uživatel může napsat cokoliv, nevalidovaná hodnota putuje do databáze.
8. **Žádný systém kurzů** – aplikace neumí převádět částky mezi měnami, takže není možné srovnávat leady v různých měnách, ani vykazovat souhrnné statistiky v reportech.

---

## Cílový stav (to-be)

Systém měn bude tvořen čtyřmi vzájemně provázanými vrstvami:

```
┌─────────────────────────────────────────────────────────────────────────┐
│  1. Workspace default currency & locale  (Firm model + Owner settings) │
│  2. Exchange Rate Engine                 (auto ECB + manuální kurzy)   │
│  3. Per-record currency + canonical amt  (Lead, Proposal, Expense, …)  │
│  4. useMoney composable + UI komponenty  (formátování, vstup, výběr)   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Fáze 1 – Backend: Workspace výchozí měna a locale

### 1.1 Rozšíření modelu `Firm`

Přidat tři pole do `firms/models.py`:

```python
default_currency = models.CharField(
    max_length=3,
    default="CZK",
    help_text="ISO 4217 currency code used as the reporting currency for this workspace."
)
number_locale = models.CharField(
    max_length=10,
    default="cs-CZ",
    help_text="BCP 47 locale tag controlling number/currency formatting (e.g. 'cs-CZ', 'en-US')."
)
exchange_rate_mode = models.CharField(
    max_length=10,
    choices=[("auto", "Automatic (ECB)"), ("manual", "Manual rates")],
    default="auto",
    help_text="How exchange rates are sourced for this workspace."
)
```

- `default_currency` – ISO 4217 třímístný kód. Slouží jako **reportingová měna** – do ní se přepočítávají všechny záznamy pro statistiky.
- `number_locale` – BCP 47 tag. Řídí, jak se čísla zobrazují v UI (oddělovač tisíců, desetinný oddělovač, pozice symbolu měny). Defaultně se nastavuje automaticky spolu s `default_currency` (CZK → `cs-CZ`, EUR + DE → `de-DE`, EUR + FR → `fr-FR`, USD → `en-US` atd.), ale Owner může nastavit odděleně.
- `exchange_rate_mode` – přepíná mezi automatickým stahováním kurzů z ECB a ručně zadanými kurzy Ownerem. Viz Fáze 3 a 4.
- Výchozí hodnoty zajistí zpětnou kompatibilitu – žádná změna chování stávajících dat.
- Přidat Django migraci.

### 1.2 Serializace do API `/api/v1/firms/`

Rozšířit `FirmOut` Ninja schéma:
```python
class FirmOut(Schema):
    id: int
    name: str
    slug: str
    # ... stávající pole ...
    default_currency: str
    number_locale: str
    exchange_rate_mode: str  # "auto" | "manual"
```

Přidat `default_currency`, `number_locale`, `exchange_rate_mode` do `PATCH /api/v1/firms/{id}/` vstupního schématu `FirmIn`. Přístup jen pro role `owner` a `admin`.

### 1.3 Výchozí měna při vytváření záznamů

Pole `currency` na modelech `Lead`, `Proposal`, `Expense`, `Revenue` si ponechají svou vlastní hodnotu. Při vytvoření záznamu přes API **bez explicitně zadané měny** se použije `request.firm.default_currency` místo hardcoded `"CZK"`. Toto se řeší v API handlerech (Django Ninja `create` funkcích), nikoliv na úrovni modelu – DB `default="CZK"` zůstane kvůli starším záznamům a přímým DB operacím.

### 1.4 Statistické agregace s ohledem na měnu

Agregační endpointy (`/api/v1/dashboard/stats`, `/api/v1/reports/summary`, …) nyní sčítají hodnoty napříč různými měnami.

**Krok A – okamžitý fix (filtr, bez konverze):**
- Agregovat pouze záznamy, jejichž `currency` odpovídá `firm.default_currency`.
- Ostatní záznamy vyloučit z numerických součtů.
- Do odpovědi přidat `mixed_currencies: true` pokud existují záznamy v jiných měnách, aby UI mohlo zobrazit varování.

**Krok B – plný fix (konverze přes `canonical_amount`):**
- Každý záznam s peněžní hodnotou bude mít pole `canonical_amount` (Decimal) a `canonical_currency` (CharField = vždy `firm.default_currency` v době uložení).
- Při uložení/update záznamu se `canonical_amount` přepočítá přes Exchange Rate Engine (viz Fáze 3).
- Statistické endpointy agregují `canonical_amount` a ignorují záznamy, kde je `canonical_amount` NULL (kurz nebyl dostupný).
- Do odpovědi přidat `unconverted_count: int` – počet záznamů bez `canonical_amount`.

---

## Fáze 2 – Frontend: `useMoney` composable a UI komponenty

### 2.1 `useMoney` composable

Vytvořit `frontend-spa/src/composables/useMoney.ts`.

Composable je sdílený zdroj pravdy pro veškeré operace s penězi v celé aplikaci. Interně čerpá z `useFirmStore().activeFirm` – žádná komponenta neřeší locale nebo defaultní měnu sama.

```typescript
export function useMoney() {
  const firmStore = useFirmStore()

  // Výchozí měna workspace (ISO 4217)
  const firmCurrency = computed(() =>
    firmStore.activeFirm?.default_currency ?? 'CZK'
  )

  // Locale pro Intl.NumberFormat (BCP 47)
  const firmLocale = computed(() =>
    firmStore.activeFirm?.number_locale ?? 'cs-CZ'
  )

  // Výstup: "12 500,00 Kč" nebo "$12,500.00"
  function formatAmount(n: number | string, currency = firmCurrency.value): string {
    return new Intl.NumberFormat(firmLocale.value, {
      style: 'currency',
      currency,
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(Number(n))
  }

  // Výstup bez symbolu: "12 500,00" (pro tabulkové sloupce kde symbol je v hlavičce)
  function formatAmountPlain(n: number | string): string {
    return new Intl.NumberFormat(firmLocale.value, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(Number(n))
  }

  // Parsování lokalizovaného stringu na number
  // "12 500,50" → 12500.50 (pro cs-CZ)
  // "12,500.50" → 12500.50 (pro en-US)
  function parseMoney(s: string): number {
    const parts = new Intl.NumberFormat(firmLocale.value).formatToParts(1111.1)
    const decimal = parts.find(p => p.type === 'decimal')?.value ?? '.'
    const clean = s
      .replace(new RegExp(`[^0-9${escapeRegex(decimal)}\\-]`, 'g'), '')
      .replace(decimal, '.')
    return parseFloat(clean) || 0
  }

  // Seřazený seznam dostupných měn pro <CurrencySelect>
  const currencies = computed(() => SUPPORTED_CURRENCIES)

  return { firmCurrency, firmLocale, formatAmount, formatAmountPlain, parseMoney, currencies }
}
```

### 2.2 `CurrencySelect` komponenta

Vytvořit `frontend-spa/src/components/CurrencySelect.vue`.

- Searchable `<select>` nebo combobox s předvoleným seznamem měn (viz seznam dole).
- Zobrazuje: kód + přeložený název dle aktuálního jazyka UI (CS: „CZK – Česká koruna", EN: „CZK – Czech Koruna").
- Props: `modelValue: string`, `disabled?: boolean`.
- Emit: `update:modelValue`.
- Výchozí hodnota se **nevyplňuje** v komponentě – volající (view/composable) předává `firmCurrency` jako výchozí. Tím se zabrání opakovanému hardcodování.
- Nahrazuje všechny `<input type="text" placeholder="CZK">` a `<option>CZK</option><option>EUR</option>` fragmenty napříč celou aplikací.

### 2.3 `MoneyInput` komponenta

Vytvořit `frontend-spa/src/components/MoneyInput.vue`.

- Specializovaný input pro zadávání peněžních částek.
- Props: `modelValue: number | null`, `currency: string`, `locale?: string`, `min?: number`, `max?: number`, `placeholder?: string`.
- **Chování při focus:** zobrazí čisté číslo v lokalizovaném formátu bez symbolu (umožní přímou editaci).
- **Chování při blur:** zobrazí lokalizovaný formát s oddělovači a symbolem měny.
- Validuje vstup – odmítá nečíselné znaky, upozorní na zápornou hodnotu pokud `min=0`.
- Interně volá `parseMoney` z `useMoney` při každé změně, emituje `number | null`.
- Volitelně zobrazuje symbol měny jako suffix/prefix dle locale (Kč suffix pro cs-CZ, $ prefix pro en-US).

### 2.4 Refaktoring existujících pohledů

Každý soubor je samostatný úkol. Pořadí dle dopadu:

| Soubor | Konkrétní změny |
|--------|-----------------|
| `LeadsView.vue` | `ref('CZK')` → `useMoney().firmCurrency`; `<input type="text" maxlength="3">` → `<CurrencySelect>`; `Intl.NumberFormat(undefined…)` → `formatAmount` |
| `ProposalsView.vue` | `ref('CZK')` → `firmCurrency`; `<option>CZK/EUR/USD</option>` → `<CurrencySelect>` |
| `ProposalBuilderView.vue` | `fmt()` local fn → `formatAmountPlain`; `CURRENCIES = ['CZK',…]` const → `currencies` z composable; `ref('CZK')` → `firmCurrency`; `unit_price` inputy → `<MoneyInput>` |
| `StreamlineCreateModal.vue` | totéž jako ProposalsView |
| `ReportsView.vue` | `formatMoney` local fn → `formatAmount`; `ref({currency: 'CZK'})` → `firmCurrency`; amount inputy → `<MoneyInput>` |
| `PublicProposalView.vue` | `fmt()` → `formatAmountPlain`; `{{ proposal.currency }}` suffix → integrovaný do `formatAmount` |
| `CustomerDetailView.vue` | `.toFixed(2)` → `formatAmountPlain`; holé `{{ value }} {{ currency }}` → `formatAmount(value, currency)` |
| `DashboardView.vue` | `Intl.NumberFormat(undefined…)` → `formatAmount`; doplnit varování při `mixed_currencies: true` z API |

### 2.5 Překlady názvů měn

Do každého locale souboru (`cs.json`, `en.json`, `de.json`, `pl.json`) přidat sekci `currencies`:

```json
"currencies": {
  "CZK": "Česká koruna",
  "EUR": "Euro",
  "USD": "Americký dolar",
  ...
}
```

`CurrencySelect` použije `t('currencies.' + code)` pro zobrazení názvu.

---

## Fáze 3 – Nastavení workspace: měna a formát čísel (Owner UI)

V sekci nastavení firmy (dostupné pouze pro role `owner` a `admin`) přidat panel **„Měny a formátování"**.

### 3.1 Výchozí měna reportingu

- `<CurrencySelect>` pro volbu `default_currency`.
- Live preview: při výběru se okamžitě zobrazí ukázkový formát „Takto bude zobrazena částka 12 500,50: **12 500,50 Kč**".
- Varování při změně: „Změna výchozí měny nezmění existující záznamy. Částky v jiných měnách budou přepočítány dle aktuálního kurzu při příštím uložení."
- Uloží se do `PATCH /api/v1/firms/{id}/` → pole `default_currency`.

### 3.2 Formát čísel

- Výběr locale ze seznamu předvoleb (automaticky spárováno s výběrem měny, ale editovatelné):
  - `cs-CZ` → ukázka: „12 500,50 Kč"
  - `de-DE` → ukázka: „12.500,50 €"
  - `en-US` → ukázka: „$12,500.50"
  - `pl-PL` → ukázka: „12 500,50 zł"
  - `fr-FR` → ukázka: „12 500,50 €"
- Uloží se do `PATCH /api/v1/firms/{id}/` → pole `number_locale`.

### 3.3 Zdroj kurzů

- Toggle / radio skupina: **„Automatické kurzy (ECB)"** vs. **„Ruční kurzy"**.
- Uloží se do `PATCH /api/v1/firms/{id}/` → pole `exchange_rate_mode`.
- Při volbě „Automatické kurzy" se zobrazí informace o zdroji a čas poslední aktualizace.
- Při volbě „Ruční kurzy" se zobrazí tabulka pro správu kurzů (viz Fáze 4.3).

---

## Fáze 4 – Exchange Rate Engine

Exchange Rate Engine je jádrem celého systému konverze. Skládá se z datového modelu, zdrojů kurzů a API pro přepočet.

### 4.1 Datový model `FirmExchangeRate`

Model je **scopován na Firm** – každá firma má vlastní sadu kurzů (manuálních nebo přepsaných automatických).

```python
# crm/models.py (nebo firms/models.py)

class FirmExchangeRate(models.Model):
    """
    Exchange rate for a specific currency pair, scoped to a Firm.

    Priority logic:
    - If firm.exchange_rate_mode == 'manual': only manual rates are used.
    - If firm.exchange_rate_mode == 'auto': system-wide ECB rates are used,
      but a firm-level manual override takes precedence for a given pair.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    firm = models.ForeignKey(
        "firms.Firm",
        on_delete=models.CASCADE,
        related_name="exchange_rates",
    )
    from_currency = models.CharField(max_length=3)   # ISO 4217, např. "USD"
    to_currency = models.CharField(max_length=3)     # ISO 4217, musí = firm.default_currency
    rate = models.DecimalField(max_digits=20, decimal_places=8)
    # Kolik jednotek from_currency = 1 jednotka to_currency
    # Příklad: USD→CZK, rate=23.15 znamená 1 USD = 23,15 CZK

    source = models.CharField(
        max_length=10,
        choices=[("manual", "Manual"), ("ecb", "ECB Auto")],
        default="manual",
    )
    valid_from = models.DateField(
        help_text="Rate is effective from this date (inclusive)."
    )
    valid_to = models.DateField(
        null=True, blank=True,
        help_text="Rate is effective until this date (inclusive). NULL = currently active."
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        help_text="User who created this rate (NULL for system/ECB rates).",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    note = models.CharField(
        max_length=255, blank=True,
        help_text="Optional note visible to team members (e.g. 'Q1 2026 fixed rate per contract')."
    )

    class Meta:
        verbose_name = "firm exchange rate"
        verbose_name_plural = "firm exchange rates"
        ordering = ["-valid_from"]
        indexes = [
            models.Index(fields=["firm", "from_currency", "to_currency", "-valid_from"]),
        ]

    def __str__(self):
        return f"{self.from_currency}→{self.to_currency} @ {self.rate} ({self.valid_from})"
```

**Klíčové designové rozhodnutí – temporální záznamy:**
- Každý kurz má `valid_from` a `valid_to`. Aktuálně platný kurz má `valid_to=NULL`.
- Při zadání nového manuálního kurzu se starý uzavře (`valid_to = new_valid_from - 1 day`).
- Historické záznamy se nikdy nemažou – slouží pro přepočet historických dat.
- Tato temporální struktura umožní v budoucnu generovat reporty s historickými kurzy.

**Systémový model `SystemExchangeRate` (globální ECB kurzy):**

```python
class SystemExchangeRate(models.Model):
    """
    Global exchange rates fetched from ECB. Not scoped to a firm.
    Used when firm.exchange_rate_mode == 'auto' and no firm-level override exists.
    """
    base_currency = models.CharField(max_length=3, default="EUR")
    quote_currency = models.CharField(max_length=3)
    rate = models.DecimalField(max_digits=20, decimal_places=8)
    date = models.DateField()
    source = models.CharField(max_length=20, default="ecb")

    class Meta:
        unique_together = [("base_currency", "quote_currency", "date")]
        indexes = [
            models.Index(fields=["quote_currency", "-date"]),
        ]
```

### 4.2 Logika výběru kurzu (`get_rate`)

```python
# crm/money.py

def get_rate(
    firm: Firm,
    from_currency: str,
    to_currency: str,
    date: date | None = None,
) -> Decimal | None:
    """
    Returns the exchange rate from_currency → to_currency for the given date.
    
    Priority:
    1. FirmExchangeRate with source='manual' for this firm (highest priority,
       regardless of exchange_rate_mode).
    2. If exchange_rate_mode == 'auto': SystemExchangeRate from ECB.
    3. If no rate found: return None (caller handles gracefully).
    
    Cross-rate calculation:
    If direct pair (USD→CZK) is not available but both USD→EUR and EUR→CZK
    exist, calculates via EUR as pivot.
    """
    target_date = date or datetime.date.today()

    # 1. Firm manual override
    firm_rate = (
        FirmExchangeRate.objects
        .filter(
            firm=firm,
            from_currency=from_currency,
            to_currency=to_currency,
            valid_from__lte=target_date,
        )
        .filter(models.Q(valid_to__isnull=True) | models.Q(valid_to__gte=target_date))
        .order_by("-valid_from")
        .first()
    )
    if firm_rate:
        return firm_rate.rate

    # 2. Auto ECB (only if mode allows)
    if firm.exchange_rate_mode == "auto":
        sys_rate = _get_system_rate(from_currency, to_currency, target_date)
        if sys_rate:
            return sys_rate

    return None


def to_canonical(
    amount: Decimal,
    from_currency: str,
    firm: Firm,
    date: date | None = None,
) -> Decimal | None:
    """Convert amount to firm.default_currency. Returns None if rate unavailable."""
    if from_currency == firm.default_currency:
        return amount
    rate = get_rate(firm, from_currency, firm.default_currency, date)
    if rate is None:
        return None
    return (amount * rate).quantize(Decimal("0.01"))
```

### 4.3 Automatické stahování kurzů z ECB

**Celery beat task:**

```python
# crm/tasks.py

@shared_task
def fetch_ecb_exchange_rates():
    """
    Downloads daily XML feed from ECB and upserts SystemExchangeRate records.
    Runs daily at 17:00 CET (ECB publishes by ~16:00 CET).
    ECB feed URL: https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml
    Base currency: EUR.
    """
    ...
```

Celery beat schedule v `settings.py`:
```python
CELERY_BEAT_SCHEDULE = {
    "fetch-ecb-rates": {
        "task": "crm.tasks.fetch_ecb_exchange_rates",
        "schedule": crontab(hour=17, minute=30),
    },
    ...
}
```

**Postup stahování:**
1. GET `https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml`
2. Parsovat XML (ElementTree), extrahovat datum a kurzy.
3. Pro každý pár `EUR→XXX` upsert záznamu `SystemExchangeRate(base="EUR", quote=XXX, rate=…, date=…)`.
4. Pokud je datum stejné jako poslední existující záznam → skip (idempotentní).
5. Logovat výsledek (počet nových záznamů, chyby).

**Výpadek ECB:**
- Pokud stahování selže, Celery task se zopakuje (retry s exponential backoff, max 3×).
- Pokud kurz pro dnešní datum není dostupný, `get_rate` vrátí kurz z nejbližšího předchozího dne (max 7 dní zpět).
- Po 7 dnech bez čerstvého kurzu se `canonical_amount` u nových záznamů nastaví na `NULL` a admin dostane upozornění.

### 4.4 Manuální správa kurzů – Owner UI

V nastavení workspace, v záložce **„Kurzy měn"** (zobrazí se při `exchange_rate_mode = 'manual'` nebo vždy jako přehled při `'auto'`):

**Tabulka aktivních kurzů:**

| Z měny | Do měny | Kurz | Platnost od | Platnost do | Zdroj | Poznámka | Akce |
|--------|---------|------|-------------|-------------|-------|----------|------|
| USD | CZK | 23,1500 | 1. 1. 2026 | – | Ruční | Q1 2026 sazba | Upravit / Zrušit |
| EUR | CZK | 25,0000 | 1. 1. 2026 | – | Ruční | | Upravit / Zrušit |
| GBP | CZK | – | – | – | (ECB) | automaticky | – |

- V manuálním módu jsou chybějící kurzy zvýrazněny červeně (varování „Záznamy v této měně nelze přepočítat").
- V automatickém módu se zobrazují ECB kurzy jako read-only, s možností je přepsat manuální hodnotou.

**Formulář přidání/editace kurzu:**

```
Z měny:      [CurrencySelect ▼]
Do měny:     [CZK – výchozí měna, read-only]
Kurz:        [MoneyInput – počet jednotek "Do měny" za 1 "Z měny"]
             Příklad: 1 USD = [23,1500] CZK
Platný od:   [DatePicker – výchozí: dnes]
Poznámka:    [TextInput, nepovinné, max 255 znaků]
             Příklady: "Fixní kurz dle smlouvy Q1", "Dohoda s klientem XY"

[Uložit kurz]
```

**Chování při uložení:**
1. Backend zavolá `PATCH /api/v1/firms/{id}/exchange-rates/` (nebo `POST /api/v1/firms/{id}/exchange-rates/`).
2. Pokud pro daný pár (from→to) existuje aktivní kurz (`valid_to=NULL`), uzavře ho: nastaví `valid_to = new_valid_from - 1 day`.
3. Vytvoří nový záznam s `valid_from = zadané datum`, `valid_to = NULL`, `source = "manual"`, `created_by = request.user`.
4. Spustí async Celery task `recalculate_canonical_amounts_for_firm.delay(firm_id)` – přepočítá `canonical_amount` u všech záznamů od `valid_from` dopředu.

**Historie kurzů:**

Záložka „Historie" v panelu kurzů zobrazuje všechny záznamy včetně uzavřených, seřazené od nejnovějšího. Umožní přehled a audit změn kurzů. Každý historický záznam zobrazuje, kdo a kdy kurz nastavil.

### 4.5 API endpointy pro správu kurzů

```
GET    /api/v1/firms/{id}/exchange-rates/
       → seznam aktivních kurzů pro firmu
       Parametry: ?include_history=true (vrátí i uzavřené)

POST   /api/v1/firms/{id}/exchange-rates/
       → vytvoří nový manuální kurz (uzavře případný stávající)
       Body: { from_currency, rate, valid_from, note? }
       to_currency je vždy firm.default_currency

PATCH  /api/v1/firms/{id}/exchange-rates/{rate_id}/
       → editace poznámky nebo drobné opravy (rate, valid_from)
       Editace válcuje kurz – vytvoří nový, původní uzavře

DELETE /api/v1/firms/{id}/exchange-rates/{rate_id}/
       → smaže manuální kurz (nahradí ho ECB pokud mode=auto, jinak pair zůstane bez kurzu)
       Pouze pro source='manual'

GET    /api/v1/firms/{id}/exchange-rates/preview/
       → náhled přepočtu: { from_currency, amount } → { canonical_amount, rate_used, rate_date, source }
       Slouží pro live preview v UI před uložením
```

Přístup ke všem endpointům: pouze role `owner` a `admin`.

### 4.6 Přepočet `canonical_amount` při uložení záznamu

```python
# crm/models.py

class Lead(TenantModel, SoftDeleteMixin):
    # ... stávající pole ...
    value = models.DecimalField(...)
    currency = models.CharField(max_length=3, ...)

    # Nová pole pro kanonické částky
    canonical_amount = models.DecimalField(
        max_digits=20, decimal_places=2,
        null=True, blank=True,
        help_text="Value converted to firm.default_currency at time of last save."
    )
    canonical_currency = models.CharField(
        max_length=3, blank=True,
        help_text="Currency code of canonical_amount (= firm.default_currency at save time)."
    )
    canonical_rate_used = models.DecimalField(
        max_digits=20, decimal_places=8,
        null=True, blank=True,
        help_text="Exchange rate used for canonical_amount calculation."
    )
    canonical_updated_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When was canonical_amount last recalculated."
    )
```

Přepočet se spustí v `Lead.save()` pokud se změnilo `value` nebo `currency`:

```python
def save(self, *args, **kwargs):
    if self.value is not None:
        firm = self.firm
        result = to_canonical(self.value, self.currency, firm)
        self.canonical_amount = result
        self.canonical_currency = firm.default_currency
        self.canonical_updated_at = timezone.now()
    super().save(*args, **kwargs)
```

Stejná logika pro `Expense`, `Revenue`, `Proposal` (total_value).

---

## Fáze 5 – Celery task: hromadný přepočet `canonical_amount`

```python
@shared_task
def recalculate_canonical_amounts_for_firm(firm_id: str):
    """
    Recalculates canonical_amount for all financial records of a firm.
    Triggered when:
    - Owner saves a new manual exchange rate
    - Owner changes firm.default_currency
    - Manual admin action
    """
    firm = Firm.objects.get(id=firm_id)
    updated = 0
    failed = 0

    for model_class, amount_field in [
        (Lead, "value"),
        (Expense, "amount"),
        (Revenue, "amount"),
    ]:
        for obj in model_class.objects.filter(firm=firm).exclude(**{amount_field: None}):
            amount = getattr(obj, amount_field)
            result = to_canonical(amount, obj.currency, firm, date=obj.created_at.date())
            if result is not None:
                obj.canonical_amount = result
                obj.canonical_currency = firm.default_currency
                obj.canonical_updated_at = timezone.now()
                obj.save(update_fields=["canonical_amount", "canonical_currency", "canonical_updated_at"])
                updated += 1
            else:
                failed += 1

    logger.info(f"[firm={firm_id}] canonical recalc: {updated} updated, {failed} failed (no rate)")
    return {"updated": updated, "failed": failed}
```

---

## Fáze 6 – Datová migrace existujících záznamů

Po nasazení Fáze 1:

**Management command 1: `backfill_firm_currency`**
- Pro každou firmu nastaví `default_currency` dle **nejčastěji používané měny** v jejích Leadech.
- Pokud jsou záznamy v jediné měně → nastaví tu. Pokud mix → nastaví nejčastější a loguje warning.
- Nezmění stávající záznamy, jen nastaví `firm.default_currency`.

**Management command 2: `backfill_canonical_amounts`**
- Spustí `recalculate_canonical_amounts_for_firm` pro každou firmu.
- Pro záznamy, kde `currency == firm.default_currency` → `canonical_amount = amount` (rate 1:1, bez potřeby historického kurzu).
- Pro záznamy v jiné měně:
  - V automatickém módu: zkusit historický ECB kurz dle `created_at.date()`.
  - V manuálním módu (nebo pokud ECB kurz pro dané datum chybí): `canonical_amount = NULL`, loguje jako „přeskočeno".
- Na konci vypíše report: kolik záznamů přepočítáno, kolik přeskočeno, pro které firmy.

---

## Podporované měny (výchozí seznam)

| Kód | Název CS | Název EN | Název DE | Název PL |
|-----|----------|----------|----------|----------|
| CZK | Česká koruna | Czech Koruna | Tschechische Krone | Korona czeska |
| EUR | Euro | Euro | Euro | Euro |
| USD | Americký dolar | US Dollar | US-Dollar | Dolar amerykański |
| GBP | Britská libra | British Pound | Britisches Pfund | Funt brytyjski |
| PLN | Polský zlotý | Polish Zloty | Polnischer Złoty | Złoty polski |
| HUF | Maďarský forint | Hungarian Forint | Ungarischer Forint | Forint węgierski |
| CHF | Švýcarský frank | Swiss Franc | Schweizer Franken | Frank szwajcarski |
| NOK | Norská koruna | Norwegian Krone | Norwegische Krone | Korona norweska |
| SEK | Švédská koruna | Swedish Krone | Schwedische Krone | Korona szwedzka |
| DKK | Dánská koruna | Danish Krone | Dänische Krone | Korona duńska |
| RON | Rumunský leu | Romanian Leu | Rumänischer Leu | Lej rumuński |
| BGN | Bulharský lev | Bulgarian Lev | Bulgarischer Lew | Lew bułgarski |
| UAH | Ukrajinská hřivna | Ukrainian Hryvnia | Ukrainische Hrywnja | Hrywna ukraińska |
| RSD | Srbský dinár | Serbian Dinar | Serbischer Dinar | Dinar serbski |

Seznam je uložen jako konstanta `SUPPORTED_CURRENCIES` v `frontend-spa/src/composables/useMoney.ts` a v `crm/money.py`. Lze rozšířit přidáním do obou míst.

---

## Lokalizace formátování čísel

| Locale | Příklad částky | Tisíce | Des. odděl. | Symbol |
|--------|----------------|--------|-------------|--------|
| `cs-CZ` | 12 500,50 Kč | mezera | čárka | za číslem |
| `sk-SK` | 12 500,50 € | mezera | čárka | za číslem |
| `de-DE` | 12.500,50 € | tečka | čárka | za číslem |
| `en-US` | $12,500.50 | čárka | tečka | před číslem |
| `en-GB` | £12,500.50 | čárka | tečka | před číslem |
| `pl-PL` | 12 500,50 zł | mezera | čárka | za číslem |
| `fr-FR` | 12 500,50 € | mezera | čárka | za číslem |

Veškeré formátování řeší `Intl.NumberFormat` s parametry `{ style: 'currency', currency, locale: firmLocale }`. Žádné ruční formátování v komponentách.

**Automatické spárování měna → default locale:**
```typescript
const CURRENCY_DEFAULT_LOCALE: Record<string, string> = {
  CZK: 'cs-CZ',
  EUR: 'de-DE',   // Owner může přepsat na fr-FR, sk-SK, atd.
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
}
```

Při změně `default_currency` v nastavení se `number_locale` automaticky aktualizuje na default pro danou měnu, ale Owner může hodnotu přepsat.

---

## Architektura `useMoney.ts` (detailní sketch)

```typescript
// frontend-spa/src/composables/useMoney.ts

export interface CurrencyOption {
  code: string        // 'CZK'
  names: Record<string, string>  // { cs: 'Česká koruna', en: 'Czech Koruna', ... }
  defaultLocale: string          // 'cs-CZ'
}

export const SUPPORTED_CURRENCIES: CurrencyOption[] = [
  { code: 'CZK', names: { cs: 'Česká koruna', en: 'Czech Koruna', de: 'Tschechische Krone', pl: 'Korona czeska' }, defaultLocale: 'cs-CZ' },
  { code: 'EUR', names: { cs: 'Euro', en: 'Euro', de: 'Euro', pl: 'Euro' }, defaultLocale: 'de-DE' },
  // ...
]

export const CURRENCY_DEFAULT_LOCALE: Record<string, string> = {
  CZK: 'cs-CZ', EUR: 'de-DE', USD: 'en-US', GBP: 'en-GB', PLN: 'pl-PL', /* ... */
}

function escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

export function useMoney() {
  const firmStore = useFirmStore()
  const { locale: uiLocale } = useI18n()

  const firmCurrency = computed(() => firmStore.activeFirm?.default_currency ?? 'CZK')
  const firmLocale   = computed(() => firmStore.activeFirm?.number_locale ?? 'cs-CZ')

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
    const parts = new Intl.NumberFormat(firmLocale.value).formatToParts(1111.1)
    const decimal = parts.find(p => p.type === 'decimal')?.value ?? '.'
    const clean = s
      .replace(new RegExp(`[^0-9${escapeRegex(decimal)}\\-]`, 'g'), '')
      .replace(decimal, '.')
    return parseFloat(clean) || 0
  }

  // Vrací seřazený seznam s přeloženými názvy dle aktuálního UI jazyka
  const currencies = computed(() =>
    SUPPORTED_CURRENCIES.map(c => ({
      code: c.code,
      label: `${c.code} – ${c.names[uiLocale.value] ?? c.names['en']}`,
    })).sort((a, b) => a.label.localeCompare(b.label))
  )

  return { firmCurrency, firmLocale, formatAmount, formatAmountPlain, parseMoney, currencies }
}
```

---

## Prioritizovaný seznam úkolů (backlog)

### P0 – Kritické (blocker pro statistiky) ✅ HOTOVO
- [x] Přidat `default_currency`, `number_locale`, `exchange_rate_mode` do modelu `Firm` + migrace (`firms/migrations/0010_firm_currency_settings.py`)
- [x] Rozšířit `FirmOut` schema a PATCH endpoint `PATCH /api/v1/firms/{id}/currency` (jen admin/owner)
- [x] Opravit `dashboard/stats` – filtrovat na `firm.default_currency`, vrátit `mixed_currencies` flag
- [x] Opravit `erp/reports/summary` – filtrovat na `firm.default_currency`, vrátit `mixed_currencies` flag
- [x] Management command `backfill_firm_currency` (`crm/management/commands/backfill_firm_currency.py`)

### P1 – Vysoká priorita (UX + sdílená infrastruktura) ✅ HOTOVO
- [x] Vytvořit `useMoney.ts` composable (`frontend-spa/src/composables/useMoney.ts`)
- [x] Vytvořit `CurrencySelect.vue` komponent (`frontend-spa/src/components/CurrencySelect.vue`)
- [x] Vytvořit `MoneyInput.vue` komponent (`frontend-spa/src/components/MoneyInput.vue`)
- [x] Přidat i18n klíče pro názvy měn a currency settings do `cs.json`, `en.json`, `de.json`, `pl.json`
- [x] Rozšířit `FirmOut` interface v `stores/firm.ts` o `default_currency`, `number_locale`, `exchange_rate_mode`
- [x] Refaktorovat `LeadsView.vue` (text input → CurrencySelect, `Intl.NumberFormat` → `formatAmount`)
- [x] Refaktorovat `ProposalsView.vue` (hardcoded `<option>` select → CurrencySelect, `ref('CZK')` → firmCurrency)
- [x] Refaktorovat `ProposalBuilderView.vue` (CURRENCIES const → CurrencySelect, `fmt()` → `formatAmountPlain`)
- [x] Přidat sekci „Měny a formátování" do `SettingsView.vue` (měna, locale, mode toggle, live preview)

### P2 – Exchange Rate Engine ✅ HOTOVO
- [x] Model `SystemExchangeRate` + migrace (`firms/models.py`, `firms/migrations/0011_add_exchange_rate_models.py`)
- [x] Model `FirmExchangeRate` + migrace (stejné umístění)
- [x] `crm/money.py` – `get_rate()`, `to_canonical()`, `_get_system_rate()`, křížové kurzy přes EUR pivot
- [x] Celery task `fetch_ecb_exchange_rates` v `crm/tasks.py` (denní stahování ECB XML, idempotentní, retry 3×)
- [x] Celery beat schedule `fetch-ecb-exchange-rates` v `leadlab/settings.py` (17:30 UTC)
- [x] Celery task `recalculate_canonical_amounts_for_firm` v `crm/tasks.py`
- [x] API endpointy pro správu kurzů (`GET/POST/PATCH/DELETE /api/v1/firms/{id}/exchange-rates/` + preview endpoint)
- [x] Owner UI – tabulka aktivních kurzů, formulář přidání, záložka historie, editace poznámky, smazání (`SettingsView.vue`)
- [x] `canonical_amount`, `canonical_currency`, `canonical_rate_used`, `canonical_updated_at` pole na `Lead`, `ExpenseItem`, `RevenueItem` + migrace (`crm/migrations/0060_add_canonical_amount_fields.py`)
- [x] Přepočet `canonical_amount` v `Lead.save()`, `ExpenseItem.save()`, `RevenueItem.save()` (přes `_recalc_canonical` helper)
- [x] Management command `backfill_canonical_amounts` (`crm/management/commands/backfill_canonical_amounts.py`)
- [x] i18n klíče `exchangeRates` v `cs.json`, `en.json`, `de.json`, `pl.json`

### P3 – Konzistence zbývajících views ✅ HOTOVO
- [x] Refaktorovat `ReportsView.vue` (lokální `formatMoney` → `formatAmount`, `ref('CZK')` → `firmCurrency`, text inputs → `CurrencySelect`, `createProposalFromReport` hardcoded `'CZK'` → `firmCurrency`)
- [x] Refaktorovat `StreamlineCreateModal.vue` (`ref('CZK')` → `firmCurrency`, `<option>CZK/EUR/…` → `CurrencySelect`)
- [x] Refaktorovat `PublicProposalView.vue` (`fmt()` lokální `.toFixed(2)` → `formatAmountPlain` respektující locale/měnu návrhu)
- [x] Refaktorovat `CustomerDetailView.vue` (`.toFixed(2) {{ currency }}` → `formatAmountPlain`, `{{ value }} {{ currency }}` → `formatAmount`)
- [x] Refaktorovat `DashboardView.vue` (`Intl.NumberFormat(undefined…)` → `formatAmount`, přidáno `mixed_currencies` pole do `StatsData`, varování zobrazeno u pipeline karty)

### P4 – Budoucí rozšíření
- [ ] Křížové kurzy (cross-rate přes EUR pivot) v `get_rate()`
- [ ] Export kurzů do CSV/Excel (pro audit)
- [ ] Webhook notifikace při výpadku ECB (Slack/email pro adminy)
- [ ] Rozšíření seznamu podporovaných měn (USD stablecoins, exotické měny)
- [ ] Per-user locale preference (override nad firm locale)

---

## Stav implementace

### Dokončeno (Fáze P0 + P1 + P2)
**Backend:**
- `firms/models.py` – přidána pole `default_currency` (default CZK), `number_locale` (default cs-CZ), `exchange_rate_mode` (default auto)
- `firms/migrations/0010_firm_currency_settings.py` – Django migrace
- `firms/api.py` – `FirmOut` rozšíren o nová pole; `FirmCurrencyIn` schéma; endpoint `PATCH /api/v1/firms/{id}/currency` (jen admin/owner)
- `crm/api.py` – `get_stats` filtruje `pipeline_value`/`won_value` dle `firm.default_currency`, vrací `mixed_currencies` flag
- `crm/erp_api.py` – `reports_summary` filtruje `total_expenses`/`total_revenues` dle `firm.default_currency`, vrací `mixed_currencies` flag
- `crm/management/commands/backfill_firm_currency.py` – management command pro backfill defaultní měny
- `firms/models.py` – nové modely `SystemExchangeRate` (globální ECB kurzy) a `FirmExchangeRate` (per-firm manuální kurzy s temporální platností)
- `firms/migrations/0011_add_exchange_rate_models.py` – Django migrace
- `crm/money.py` – nový modul: `get_rate()`, `to_canonical()`, `_get_system_rate()`, křížové kurzy přes EUR pivot, fallback 7 dní zpět
- `crm/models.py` – `canonical_amount`, `canonical_currency`, `canonical_rate_used`, `canonical_updated_at` pole na `Lead`, `ExpenseItem`, `RevenueItem`; `_recalc_canonical()` helper; `save()` override na všech třech modelech
- `crm/migrations/0060_add_canonical_amount_fields.py` – Django migrace
- `crm/tasks.py` – `fetch_ecb_exchange_rates` (idempotentní ECB XML stahování, retry 3×, beat 17:30 UTC); `recalculate_canonical_amounts_for_firm` (hromadný přepočet canonical amounts)
- `leadlab/settings.py` – beat schedule `fetch-ecb-exchange-rates`
- `firms/api.py` – nové endpointy `GET/POST/PATCH/DELETE /api/v1/firms/{id}/exchange-rates/` + `GET /api/v1/firms/{id}/exchange-rates/preview/` (jen admin/owner)
- `crm/management/commands/backfill_canonical_amounts.py` – management command s `--firm` a `--dry-run` volbami

**Frontend:**
- `stores/firm.ts` – `FirmOut` interface rozšíren o `default_currency`, `number_locale`, `exchange_rate_mode`
- `composables/useMoney.ts` – nový sdílený composable: `firmCurrency`, `firmLocale`, `formatAmount`, `formatAmountPlain`, `parseMoney`, `currencies`; `SUPPORTED_CURRENCIES`, `CURRENCY_DEFAULT_LOCALE`
- `components/CurrencySelect.vue` – searchable combobox s podporovanými měnami
- `components/MoneyInput.vue` – specializovaný input pro částky (focus/blur, locale, prefix/suffix symbol)
- `views/LeadsView.vue` – refaktoring: `ref('CZK')` → `firmCurrency`, text input → `CurrencySelect`, `Intl.NumberFormat` → `formatAmount`
- `views/ProposalsView.vue` – refaktoring: `ref('CZK')` → `firmCurrency`, `<option>CZK/EUR/…` → `CurrencySelect`, `fmt()` → `formatAmount`
- `views/ProposalBuilderView.vue` – refaktoring: `CURRENCIES` const odstraněna, `ref('CZK')` → `firmCurrency`, `<option>` select → `CurrencySelect`, `fmt()` → `formatAmountPlain`
- `views/SettingsView.vue` – přidána sekce „Měny a formátování" (CurrencySelect, locale dropdown, live preview, exchange_rate_mode radio, uložení přes `PATCH /api/v1/firms/{id}/currency`); **přidána sekce „Kurzy měn"** (tabulka aktivních kurzů, editace poznámky, smazání, záložka historie, formulář přidání nového kurzu s CurrencySelect, preview read-only pole, recalc trigger)
- `locales/cs.json`, `en.json`, `de.json`, `pl.json` – přidány sekce `currencies` (překlady názvů měn), `currencySettings` (překlady UI labelů) a **`exchangeRates`** (překlady tabulky a formuláře kurzů)
- `views/ReportsView.vue` – refaktoring: lokální `formatMoney` → `formatAmount`, `ref('CZK')` → `firmCurrency`, text currency inputs → `CurrencySelect`, `createProposalFromReport` hardcoded `'CZK'` → `firmCurrency`
- `components/StreamlineCreateModal.vue` – refaktoring: `ref('CZK')` → `firmCurrency`, `<option>CZK/EUR/…` → `CurrencySelect`
- `views/PublicProposalView.vue` – refaktoring: lokální `fmt()` `.toFixed(2)` → `formatAmountPlain` respektující locale/měnu návrhu
- `views/CustomerDetailView.vue` – refaktoring: `.toFixed(2) {{ currency }}` → `formatAmountPlain`, `{{ value }} {{ currency }}` → `formatAmount`
- `views/DashboardView.vue` – refaktoring: `Intl.NumberFormat(undefined…)` → `formatAmount`, přidáno `mixed_currencies` pole do `StatsData`, varování zobrazeno u pipeline karty

### Příští fáze: P4 – Budoucí rozšíření
Viz sekce P4 níže. Doporučené pořadí: export kurzů do CSV, webhook notifikace při výpadku ECB, per-user locale preference.

---

## Závislosti a rizika

| Riziko | Dopad | Mitigace |
|--------|-------|----------|
| Statistiky sčítají různé měny | Statisticky nesprávné hodnoty | P0: filtr na `firm.default_currency`, vrátit `mixed_currencies` flag |
| ECB feed je nedostupný | Nové záznamy bez `canonical_amount` | Retry 3×, fallback na kurz z posledních 7 dní, admin notifikace |
| Owner zadá chybný manuální kurz | Nesprávné statistiky | Live preview v UI; po uložení se spustí recalc task; history umožní rollback |
| Owner změní `default_currency` | Canonical amounts v jiné měně než nová default | Spustit `recalculate_canonical_amounts_for_firm`; jasná UI notifikace; existující záznamy zachovat původní `currency` |
| `canonical_amount = NULL` pro část záznamů | Neúplné statistiky | `unconverted_count` v API odpovědi; varování v UI; manuální kurz řeší problém |
| `Intl.NumberFormat` parsování vstupů | Chybný parsing (různé locale) | Unit testy `parseMoney` pro cs-CZ, en-US, de-DE, pl-PL; fallback `parseFloat` |
| Breaking change `FirmOut` API | Frontend crash při deployi | Nová pole jako optional s default hodnotami; postupný rollout |
| Temporální kurzy – nekonzistence při editaci | Záznamy ukazují jiný kurz než byl v době zadání | `canonical_rate_used` uložen u záznamu; editace kurzu neovlivní historické záznamy zpětně za `valid_from` |

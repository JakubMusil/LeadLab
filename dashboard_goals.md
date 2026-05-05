# Dashboard – revize a plán vylepšení

> Cíl: po přechodu z **Lead** na **Record / Category / Stage** systém kompletně
> zrevidovat widgety na úvodní stránce (`/app` → `DashboardView.vue`) tak, aby
> odpovídaly aktuálnímu pipeline modelu, podporovaly **uživatelem definované
> kategorie záznamů** a přinesly další funkce, které uživatelé v dashboardu
> ocení.
>
> Tento dokument je zároveň **plán** i **deník postupu**. Pod každou fází je
> sekce *Status / Postup*, kterou agent průběžně aktualizuje. Na konci každé
> dokončené dávky práce se v sekci **„Co bude následovat“** uvádí další krok.

---

## 1. Analýza současného stavu

Soubor: `frontend-spa/src/views/DashboardView.vue` (≈ 617 řádků).
API: `GET /api/v1/crm/stats` (`crm/api.py` ≈ ř. 4816–4884) a
`GET/PUT /api/v1/crm/dashboard-layout` (uloženo na `User`).

### 1.1 Stávající widgety

| ID                    | Popis                                                                                  |
|-----------------------|----------------------------------------------------------------------------------------|
| `stat_cards`          | 4 karty: Celkem záznamů, Zákazníci, Pipeline (hodnota + Won), Otevřené úkoly + overdue |
| `quick_create_record` | Inline formulář (Title + Status + Value)                                               |
| `pipeline_chart`      | Bar chart záznamů podle **legacy** `RecordStatus` (new/contacted/proposal/…)           |
| `recent_activity`     | Posledních 10 aktivit napříč firmou (timeline)                                         |
| `my_top_records`      | 5 mých aktivních záznamů s nejvyšším `score`                                           |
| `status_breakdown`    | „Pills“ s počty podle stejného legacy statusu, prokliky filtrují `?status=…`           |

### 1.2 Hlavní problémy / mezery

1. **Hardcoded statusy** – frontend používá `RECORD_STATUSES` (`new, contacted,
   proposal, negotiation, won, lost, canceled`) a obarvení v `STATUS_COLORS` /
   `STATUS_LABELS`. Aktuální systém staví na `Category` + `Stage`
   (`is_terminal`, `is_won`, vlastní barva) definovaných na firmu. **Status zůstává
   jako globální „top-level“ příznak**, ale skutečnou pipeline tvoří stages.
   → Widgety pipeline/status jsou polopravdivé pro firmy s vlastními kategoriemi.

2. **Žádný pohled per kategorie** – není možné vidět „Obchodní kategorie vs.
   Reklamace“ nebo „Projekty A vs. B“. Firmy s více kategoriemi vidí jen
   souhrnnou trubku.

3. **Žádný stage funnel** – chybí klasický CRM **funnel** (záznamy / hodnota
   v jednotlivých `Stage` zvolené kategorie) včetně konverzí mezi stages.

4. **„Quick create“ není category-aware** – formulář vytváří záznam jen
   s `title/status/value`. Po vytvoření chybí jak `category_id`, tak
   `current_stage_id`, takže nový záznam se neobjeví na žádném pipeline boardu.
   Label „Rychlé vytvoření **leadu**“ (`qcCreated`/`qcFailed`/`quickCreateLead`)
   v překladech ještě reflektuje starou doménu.

5. **i18n drobnosti** – v `cs.json` jsou ještě klíče `totalLeads`, `myTopLeads`,
   `myTopLeadsEmpty`, `quickCreateLead`. Texty jsou už „Záznam…“, ale klíče
   matou. Některé klíče (`noClosedLeads`, `noStatusHistory`, `noTrendData`,
   `myTopLeads`, `myTopLeadsEmpty`) **nejsou nikde použity** – pozůstatky.

6. **Recent activity** – lineární výpis 10 položek bez filtru (typ, autor,
   kategorie). U firmy s mnoha aktivitami widget rychle „zestárne“.

7. **My top records** – řadí podle `score`, ale **nereflektuje pipeline
   progress** (např. záznam ve stage „Realizace“ s nulovým skóre je často
   důležitější). Skóre v aktuálním systému často není nastaveno.

8. **Žádný úkol-centric widget** – v kartě je jen souhrn počtu a overdue;
   uživatel nevidí, co má dnes/zítra dělat.

9. **Žádný checkpoint / deadline widget** – `Checkpoint` model existuje
   (`record.checkpoints`), ale dashboard ho ignoruje.

10. **Žádný trend** – chybí 7/30denní vývoj (vytvořeno, vyhráno, prohráno,
    aktivit). Za měsíc nelze říct, jestli se firmě daří lépe nebo hůře.

11. **Žádný Win/Loss** – konverzní rate je jen jedno číslo schované pod
    „Total leads“. Chybí win-rate, ø doba do uzavření, top důvody ztrát.

12. **Žádné per-uživatelské zaměření kromě „my top records“** – manažer nevidí
    výkon týmu, řadový uživatel nevidí, kde má rezervy.

13. **Layout je vertikální stack** – widgety jsou v 1 sloupci napříč šířkou,
    s pevně daným seskupením `pipeline_chart` + `recent_activity`. Žádná
    skutečná „grid“ konfigurace (šířka, výška).

14. **Žádná per-widget nastavení** – nelze říct „chart pro kategorii X“,
    „top records pro celou firmu (manažerský pohled)“ atd.

15. **Stats endpoint je „one-size-fits-all“** – počítá vše bez ohledu na to, co
    je viditelné. Žádná podpora pro range / scope (kategorie, uživatel,
    interval). Měna je řešena „same currency only“ s warning bannerem; chybí
    využití `canonical_amount` pro mixed-currency report.

---

## 2. Návrh cílového řešení

### 2.1 Vodicí principy

- **Driven by pipeline configuration** – kde vidíme „status“, ukážeme buď
  `Stage` zvolené kategorie, nebo top-level `RecordStatus`, nikdy ne mix.
- **Category-aware vždy** – widgety mají scope `all categories` /
  `single category`. Default = první aktivní kategorie nebo „all“.
- **Owner-aware** – přepínač `Můj pohled` / `Celá firma` (manažer/admin) tam,
  kde to dává smysl.
- **Time-range** – globální přepínač (Dnes / 7 dnů / 30 dnů / kvartál / vlastní)
  s persistencí do `dashboard_layout`.
- **Soft persona splits** – výchozí widgety jiné pro `owner/admin` (přehledové)
  a `member` (osobní – moje úkoly, můj výkon).
- **Empty-state friendly** – každý widget má vlastní prázdný stav s CTA
  (např. „Nastavit pipeline“, „Vytvořit první kategorii“).
- **i18n napříč cs/en/de/pl** – nové klíče v `dashboard.*`, žádné nové „lead“
  klíče, deprecated klíče vyčistit.
- **Dark mode + a11y** – role/aria-labely, kontrast, klávesová obsluha
  drag & drop už máme.

### 2.2 Plánovaný katalog widgetů

> Sloupec „Replace?“ ukazuje, zda je nahrazen / sloučen některý současný widget.

| Klíč                       | Popis                                                                                           | Replace?                |
|----------------------------|-------------------------------------------------------------------------------------------------|-------------------------|
| `kpi_cards`                | Konfigurovatelné KPI: Records (active/won), Pipeline value (canonical), Win rate, Tasks, Avg cycle days, Activities (last X days). Volitelná sada karet. | ✏️ `stat_cards`          |
| `category_overview`        | Dlaždice za každou aktivní `Category`: # záznamů, hodnota, % ve win-stage, sparkline 30 dnů. Click → filtr záznamů na danou kategorii. | 🆕                       |
| `stage_funnel`             | Funnel pro **zvolenou kategorii** (volba v hlavičce widgetu): počet a hodnota v každé stage + meziúrovňová konverze. | ✏️ `pipeline_chart`      |
| `record_status_chart`      | Volitelný „klasický“ bar chart počtu záznamů podle `RecordStatus` (kompatibilita / firmy bez vlastní pipeline). | ✏️ `pipeline_chart`      |
| `quick_create_record`      | Vylepšený formulář: Category → Stage (závislé) → Title → Value (currency) → Owner (admin). Po vytvoření redirect/preview. | ✏️ stávající             |
| `my_day`                   | Sloučený osobní pohled: Dnes/Po termínu/Tento týden – `Task` + `Checkpoint` v jednom feedu, s rychlým ✓ a snooze. | 🆕 (rozšíření Tasks)     |
| `my_top_records`           | Top moje **otevřené** záznamy. Řadit lze: skóre / hodnota / poslední aktivita / nejdéle bez aktivity. | ✏️ stávající             |
| `stale_records`            | „Záznamy bez aktivity > N dnů“ (default 14), filtr by category/owner. | 🆕                       |
| `recent_activity`          | Filtrovatelný feed (typ, autor, kategorie); skupinování po dnech; lazy-load stránkování. | ✏️ stávající             |
| `activity_heatmap`         | Týdenní heatmapa aktivit (typ × den, nebo uživatel × den) – vizualizace tempa práce. | 🆕                       |
| `win_loss`                 | Win-rate gauge + breakdown důvodů ztrát (`status_change` metadata + free text), ø cycle time. | 🆕                       |
| `pipeline_trend`           | 30/90denní křivka: vytvořeno / vyhráno / hodnota pipeline. | 🆕                       |
| `upcoming_checkpoints`     | Nejbližší checkpointy napříč mými / firemními záznamy (date, record). | 🆕 (využití `Checkpoint`)|
| `team_leaderboard` (admin) | Žebříček uživatelů: # vyhráno / hodnota / aktivita za zvolené období. | 🆕                       |
| `saved_view`               | Univerzální „výřez“ libovolného saved view ze stránky Records (top N řádků z uloženého filtru). | 🆕 (volitelné)           |
| `setup_progress`           | Onboarding banner povýšený na widget – progres nastavení (kategorie, importy, integrace). | ✏️ stávající banner      |

> `status_breakdown` (pills) — zachováme jako sub-feature `record_status_chart`
> nebo zrušíme (decision v Phase 1 review).

### 2.3 Per-widget nastavení (uloženo v `dashboard_layout`)

Rozšíření schématu jednoho prvku layoutu:

```jsonc
{
  "id": "stage_funnel",
  "visible": true,
  "order": 3,
  "size": { "w": 2, "h": 2 },          // grid units, optional
  "config": {
    "category_id": "uuid|null",
    "scope": "mine|firm",
    "range": "7d|30d|90d|qtd|custom",
    "sort": "score|value|stale",
    "limit": 5
  }
}
```

Backend toleruje neznámá pole (forward-compat). Frontend default-fuje chybějící
hodnoty.

### 2.4 API změny

Přidat / rozšířit:

- `GET /api/v1/crm/stats` – nepovinné query parametry:
  - `range=7d|30d|90d|ytd|all`
  - `category_id=<uuid>` (filtruje pipeline_value, status counts, activities)
  - `owner_id=<uuid|me>` (per-uživatel scope)
  - V odpovědi přidat: `pipeline_value_canonical`, `won_value_canonical`,
    `avg_cycle_days`, `created_in_range`, `won_in_range`, `lost_in_range`.

- `GET /api/v1/crm/dashboard/category-overview` – list kategorií +
  agregace (records_total, records_open, value_open_canonical, value_won_canonical,
  win_rate, sparkline 30d).

- `GET /api/v1/crm/dashboard/stage-funnel?category_id=…&range=…` – pole stages
  s `count`, `value`, `value_canonical`, `conversion_to_next`.

- `GET /api/v1/crm/dashboard/trend?metric=created|won|value&range=…` – timeseries
  (den / týden).

- `GET /api/v1/crm/dashboard/my-day` – konsolidace `Task` + `Checkpoint`
  pro `request.user`, group by *overdue / today / this_week*.

- `GET /api/v1/crm/dashboard/stale-records?days=14&category_id=…` – top N
  záznamů bez aktivity.

- `GET /api/v1/crm/dashboard/team-leaderboard?range=…` – per-user agregáty
  (pouze pro `owner/admin`).

- `GET /api/v1/crm/dashboard/checkpoints?upcoming_days=14` – seznam checkpointů.

Sdílení helperu pro **canonical-money** agregace v `crm/money.py` (už existuje
`canonical_amount` na PipelineRecord).

### 2.5 Frontend foundation

- Vytvořit `frontend-spa/src/components/dashboard/` adresář a každý widget jako
  samostatnou komponentu (`KpiCardsWidget.vue`, `StageFunnelWidget.vue`, …).
- `DashboardView.vue` se zjednoduší na **layout host** + registr widgetů.
- Sdílený composable `useDashboardWidget(id)` – načte/uloží `config`, poskytne
  `range`, `categoryId`, `scope` jako reaktivní reference.
- Použít `usePipelineStore` pro seznam kategorií / stages (cache).
- Použít `useMoney` (`canonical_amount` pro mixed currencies) místo „same
  currency only“.

### 2.6 i18n úklid

- Přejmenovat klíče v `dashboard.*`:
  `totalLeads → totalRecords`, `myTopLeads → myTopRecords` (klíč
  `myTopRecords` už je použit ve view, ale v cs.json je jen `myTopLeads` –
  bug → opravit), `quickCreateLead → quickCreateRecord`,
  `qcCreated/qcFailed` – sjednotit na „Záznam…“.
- Smazat nepoužívané klíče (`noClosedLeads`, `noStatusHistory`, `noTrendData`,
  `myTopLeads`, `myTopLeadsEmpty`) **až poté co je potvrdíme grepem**.
- Zachovat backward-compat fallback po jeden release (v `t()` zkusit nový,
  pak starý) pokud uživatelské překlady nejsou hotové ve všech jazycích.
- Lokalizace ve všech 4 souborech (`cs`, `en`, `de`, `pl`).

---

## 3. Fáze realizace

> Každá fáze je samostatný PR / dávka. Po dokončení fáze sem agent zapíše
> shrnutí a co bude následovat.

### Fáze 0 — Plán a souhlas *(✅ hotovo)*
- ✅ Sepsat tento dokument.
- ✅ Uživatel potvrdil prioritizaci a odpovědi (viz § 4).

### Fáze 1 — Backend rozšíření `/stats` + nové endpointy
- Rozšířit `StatsOut` o canonical hodnoty, range / category / owner filtry.
- Implementovat `category-overview`, `stage-funnel`, `trend`, `my-day`,
  `stale-records`, `checkpoints`, `team-leaderboard`.
- Unit testy v `crm/tests/test_dashboard_*.py`.
- Žádný frontend dopad (kromě toho, že stávající `/stats` zůstane funkční).

### Fáze 2 — Frontend foundation a refactor stávajících widgetů
- Vytvořit `components/dashboard/*` strukturu, přesunout stávající 6 widgetů
  do samostatných komponent.
- Zavést per-widget `config` v layoutu (forward-compat schéma).
- `quick_create_record` rozšířit o `category` + `stage` (závislé selecty),
  validovat dle `CategoryField` (required/visible).
- Vyčistit `RECORD_STATUSES` hardcoding tam, kde už je nahrazen stage daty.
- i18n úklid + nové klíče.

### Fáze 3 — Nové „kategorie & stage“ widgety *(✅ hotovo)*
- `category_overview`
- `stage_funnel` (s konverzemi)
- `record_status_chart` zachovaný jako legacy/optional.

### Fáze 4 — Akční widgety
- `my_day` (Tasks + Checkpoints feed s ✓/snooze)
- `stale_records`
- `upcoming_checkpoints`

### Fáze 5 — Analytika
- `pipeline_trend`
- `win_loss`
- `activity_heatmap`
- `team_leaderboard` (admin gated)

### Fáze 6 — UX vylepšení
- Globální range picker v hlavičce dashboardu.
- 12-column responsive grid (volitelně knihovna `vue-grid-layout` nebo CSS grid
  + tailwind), uložení šířky/výšky widgetu.
- Light/dark a mobile review.
- Onboarding tour pro nový dashboard.

### Fáze 7 — Polishing & cleanup
- Smazat nepoužívané i18n klíče.
- Dokumentace v `docs/` (pokud projekt má) nebo screenshoty v PR.
- E2E test pokrývající custom layout + per-widget config.

---

## 4. Rozhodnutí uživatele (zafixováno 2026-05-05)

1. **MVP rozsah** → **všechny** widgety z katalogu § 2.2, nic neodkládáme.
2. **Defaultní dashboard** → **jeden** výchozí layout, který si uživatel
   následně přizpůsobí per-user. Žádné dva oddělené default dashboardy
   (admin vs. member). Místo toho widgety klasifikujeme dle role:
   - `audience: "all"` – default vidí každý.
   - `audience: "admin"` – default vidí jen `owner`/`admin` (manažerské
     widgety: `team_leaderboard`, `setup_progress`, `win_loss`,
     `category_overview` v scope `firm`, …). Worker je má **k dispozici**
     v editoru layoutu (visible=false), ale ve výchozím stavu skryté.
3. **Range picker** → **globální v hlavičce dashboardu** + **per-widget
   override** (každý widget si může držet vlastní `range` v configu).
4. **Mixed currencies** → vždy **canonical** (firm default currency),
   tooltip s breakdown podle nativních měn.
5. **Grid vs. stack** → rozhodnuto **lehký 12-col CSS grid**
   (Tailwind `grid-cols-12` + per-widget `colSpan`/`rowSpan`),
   bez externí knihovny `vue-grid-layout`. Důvody: minimalizace bundle,
   skvěle se kombinuje s existujícím `vue-draggable-plus`, jednodušší dark
   mode/a11y, méně runtime práce. Pokud později vyvstane potřeba volného
   resize gripperu, doplníme – schéma `size:{w,h}` to už podporuje.

---

## 5. Deník postupu

### 2026-05-05 — Fáze 0
- Naskenován `DashboardView.vue` a `/api/v1/crm/stats`, modely
  `Category/Stage/CategoryField/Checkpoint/PipelineRecord`.
- Identifikováno 15 mezer (viz § 1.2).
- Navrženo 16 widgetů v cílovém katalogu (§ 2.2), API rozšíření a fázování.
- **Rozhodnutí uživatele zaneseno do § 4** (všechny widgety v MVP, single
  default layout s role-based visibility, globální range + per-widget
  override, canonical měny, 12-col CSS grid).

### 2026-05-05 — Fáze 1 (start)
- Plán: rozšířit `GET /api/v1/crm/stats` o query parametry
  `range / category_id / owner_id` a přidat canonical hodnoty
  + `avg_cycle_days`, `created_in_range`, `won_in_range`, `lost_in_range`.
- Postupně přidat `/dashboard/category-overview`, `/stage-funnel`,
  `/trend`, `/my-day`, `/stale-records`, `/checkpoints`,
  `/team-leaderboard` (admin only).
- Testy doplnit do `crm/tests.py` (samostatná třída `DashboardAPITest`).
- **Co bude následovat** (po dokončení backend Fáze 1): Fáze 2 –
  refactor `DashboardView.vue` na adresář `components/dashboard/*`,
  zavedení per-widget config schématu a globálního range pickeru.

### 2026-05-05 — Fáze 1 (✅ hotovo, backend)

Implementováno v `crm/api.py`:

- **`GET /api/v1/crm/stats`** rozšířen o query parametry `range`
  (`7d|30d|90d|qtd|ytd|all`), `category_id`, `owner_id` (UUID nebo `me`).
  V odpovědi přidáno: `pipeline_value_canonical`, `won_value_canonical`,
  `canonical_currency`, `avg_cycle_days`, `created_in_range`,
  `won_in_range`, `lost_in_range`, `range`, `currency_breakdown[]`
  (per-currency value + canonical → pro tooltip).
  Backwards-compat: bez parametrů se chová identicky jako dosud
  (kromě nově přidaných polí, která jsou aditivní).
- **`GET /api/v1/crm/dashboard/category-overview`** – per-category
  agregace (`records_total/open/won`, `value_open_canonical`,
  `value_won_canonical`, `win_rate`, `sparkline[30]`) +
  `uncategorized` bucket pokud existují záznamy bez kategorie.
- **`GET /api/v1/crm/dashboard/stage-funnel?category_id=&range=&owner_id=`**
  – stages dané kategorie s `count`, `value_canonical`,
  `conversion_to_next` (clamped 0..1). Bez `category_id` se vezme
  první aktivní kategorie. 404 pro neznámou kategorii.
- **`GET /api/v1/crm/dashboard/trend?metric=&range=&category_id=&owner_id=`**
  – timeseries po dnech. Metriky: `created | won | lost | value_won
  | value_pipeline | activities`. Default `created`, default range `30d`.
- **`GET /api/v1/crm/dashboard/my-day`** – `Task` + `Checkpoint` přiřazené
  aktuálnímu uživateli, bucketed do `overdue / today / this_week`.
- **`GET /api/v1/crm/dashboard/stale-records?days=&category_id=&owner_id=&limit=`**
  – otevřené záznamy bez aktivity > N dnů (default 14).
- **`GET /api/v1/crm/dashboard/checkpoints?upcoming_days=&scope=mine|firm`**
  – nejbližší nezavřené checkpointy.
- **`GET /api/v1/crm/dashboard/team-leaderboard?range=`**
  – per-user agregáty (`won_count`, `won_value_canonical`,
  `activities_count`, `records_open`). Vyžaduje role
  owner/admin (jinak 403).

**Testy:** `crm.tests.DashboardAPITest` – 16 testů, všechny ✅ green.
Pokrývají: nové filtry na `/stats`, category-overview, stage-funnel
(včetně 404 a default kategorie), trend (default + neznámá metrika),
my-day (overdue/today/this_week + checkpointy), stale-records,
checkpoints, team-leaderboard (admin OK / worker 403).

> **Drobnost:** parametr `range` v API kolidoval s built-in `range()`
> v Pythonu – řešeno přes `Query(None, alias="range")` + parametr
> jménem `range_` v signature funkce (ninja standardní pattern).

### 2026-05-05 — Fáze 2 (✅ hotovo, frontend foundation)

Implementováno:

- **Pinia store `useDashboardLayoutStore`** (`frontend-spa/src/stores/dashboard.ts`):
  - Rozšířené schéma `WidgetConfig` o `size?: {w,h}`, `config?: WidgetConfigOptions`,
    `audience?: 'all'|'admin'`.
  - Typ `WidgetConfigOptions` s poli `category_id`, `scope`, `range`, `sort`, `limit`.
  - Metody `loadLayout`, `saveLayout`, `toggleWidget`, `onDragEnd`,
    `getWidgetConfigOptions`, `updateWidgetConfigOptions`.
  - `DEFAULT_WIDGETS` přesunut sem (z `DashboardView.vue`).

- **Composable `useDashboardWidget(id)`** (`frontend-spa/src/composables/useDashboardWidget.ts`):
  - Poskytuje reaktivní `config`, `range`, `categoryId`, `scope`, `sort`, `limit`
    z per-widget config uloženého v `dashboard_layout`.
  - `updateConfig(updates)` pro per-widget persistenci.

- **`components/dashboard/` adresář** – 6 samostatných widgetů:
  - `StatCardsWidget.vue` – 4 KPI karty; zobrazuje `pipeline_value_canonical`
    místo `pipeline_value` pro mixed-currency firmy.
  - `PipelineChartWidget.vue` – bar chart (status × počet).
  - `RecentActivityWidget.vue` – timeline posledních aktivit.
  - `QuickCreateRecordWidget.vue` – rozšířeno o **Category** a **Stage** selecty
    (závislé: stage se resetuje při změně kategorie, non-terminal stages only);
    vytváří záznam s `category_id` + `current_stage_id`; zobrazí se jen
    pokud firma má alespoň 1 aktivní kategorii.
  - `MyTopRecordsWidget.vue` – top 5 aktivních záznamů dle score.
  - `StatusBreakdownWidget.vue` – pills s proclinkem na filtrovaný seznam.

- **`DashboardView.vue` zjednodušen** na layout host:
  - Importuje widgetové komponenty, deleguje veškerý stav na `useDashboardLayoutStore`.
  - Po quick-create volá `myTopRecordsRef?.load()` pro okamžitou aktualizaci.
  - Při mountu `fetchCategories()` z `usePipelineStore` (pro QuickCreate widget).

- **i18n úklid** (všechny 4 locale soubory – cs, en, de, pl):
  - `totalLeads → totalRecords`
  - `quickCreateLead → quickCreateRecord`
  - `myTopLeads → myTopRecords` (oprava bugu – klíč chyběl, view používalo
    `myTopRecords` ale locale měly jen `myTopLeads`)
  - `myTopLeadsEmpty → myTopRecordsEmpty` (stejný bug)
  - Smazány nepoužívané klíče: `noStatusHistory`, `noClosedLeads`, `noTrendData`
  - Přidány nové klíče: `qcCategoryLabel`, `qcCategoryPlaceholder`,
    `qcStageLabel`, `qcStagePlaceholder`

- **Testy:** 100/100 ✅ (DashboardView.spec.ts aktualizován – přidány mocky
  pro `usePipelineStore`, `window.matchMedia`, refaktorována helper funkce
  `mockApiCalls` pro správné pořadí volání).

**Co bude následovat:**
- Fáze 3 – Nové „kategorie & stage" widgety:
  - `CategoryOverviewWidget.vue` – dlaždice za každou aktivní kategorii
    (records_total/open/won, value, win_rate, sparkline 30 dnů).
  - `StageFunnelWidget.vue` – funnel pro zvolenou kategorii (stage × count/value
    + conversion_to_next), výběr kategorie v hlavičce widgetu.
  - `RecordStatusChartWidget.vue` – zachovaný „legacy" bar chart jako volitelný.


### 2026-05-05 — Fáze 3 (✅ hotovo, nové widgety)

Implementováno v `frontend-spa/src/components/dashboard/`:

- **`CategoryOverviewWidget.vue`** – volá `GET /api/v1/crm/dashboard/category-overview`.
  Grid dlaždic za každou aktivní kategorii (název, ikona, records_open, records_won,
  value_open_canonical, win_rate, SVG sparkline 30 dnů). Dlaždice klikatelná → proklik
  do `/app/records?category=<id>`. Prázdný stav s CTA „Nastavit pipeline".
  Uncategorized bucket pokud existuje.

- **`StageFunnelWidget.vue`** – volá `GET /api/v1/crm/dashboard/stage-funnel`.
  Horizontální Bar chart (Chart.js, `indexAxis: 'y'`) non-terminal stages s počty;
  tooltip ukazuje `value_canonical` a `conversion_to_next`. Výběr kategorie přes
  `<select>` v hlavičce widgetu (jen pokud firma má > 1 kategorii). Terminal stages
  zobrazeny jako barevné pills pod grafem.

- **`RecordStatusChartWidget.vue`** – legacy/optional verze, totožná logika jako
  `PipelineChartWidget`, nový widget ID `record_status_chart`. Ve výchozím layoutu
  `visible: false` (uživatel ji může zapnout v layout editoru).

**Store (`dashboard.ts`):** přidány do `DEFAULT_WIDGETS`:
`category_overview` (visible=true, order=2), `stage_funnel` (visible=true, order=3),
`record_status_chart` (visible=false, order=8). `pipeline_chart` zachován pro
backward-compat s uloženými layouty uživatelů.

**DashboardView.vue** – importy + `v-else-if` větve + `WidgetId` union + `WIDGET_LABELS` rozšířeny.

**i18n** (cs/en/de/pl) – přidány klíče: `categoryOverview`, `categoryOverviewEmpty`,
`setupPipeline`, `catRecordsOpen`, `catValueOpen`, `catWinRate`, `uncategorized`,
`stageFunnel`, `stageFunnelEmpty`, `funnelSelectCategory`, `funnelRecords`, `recordStatusChart`.

**Testy:** 100/100 frontend ✅. Žádné nové TS chyby (pre-existing chyby v jiných views).

**Co bude následovat:**
- Fáze 4 – Akční widgety:
  - `MyDayWidget.vue` – feed Tasks + Checkpoints (dnes/overdue/tento týden) s ✓/snooze.
  - `StaleRecordsWidget.vue` – záznamy bez aktivity > N dnů.
  - `UpcomingCheckpointsWidget.vue` – nejbližší checkpointy.

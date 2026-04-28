# LeadLab — Cílová architektura a Roadmapa

> **Tento dokument slouží jako master-plan pro všechny budoucí iterace LeadLab.**
> Systém je budován na modelu **Příležitost → Realizace → Správa** a skládá se ze tří pilířů:
> **CRM** (vztahy a obchod), **ERP** (provoz a nástroje) a **INSIGHT** (data a mozek).

---

## Aktuální stav (dokončeno v 1.x–3.0)

Následující funkce jsou implementovány, otestovány a nasazeny:

- [x] Vícenájemní architektura (Firm/Tenant) s rolemi Owner / Admin / Worker
- [x] Autentizace e-mailem, obnova hesla, pozvánky do týmu
- [x] **Adresář** (Customer) — CRUD kontaktů (firmy i osoby), tagy, metadata
- [x] **Příležitosti** (Lead) — 6-stavový pipeline Kanban (Nový → Kontaktovaný → Kvalifikovaný → Nabídka → Vyhráno / Prohráno)
- [x] Úkoly — globální Task Manager s kalendářem a šablonami
- [x] Nabídky (Proposals) — tvorba, PDF, veřejný link, akceptace
- [x] Aktivity — komentáře, hovory, schůzky, e-maily, nahrávání souborů
- [x] Real-time aktualizace přes WebSocket (Django Channels)
- [x] Analytika — pipeline velocity, výkon týmu, trendy konverzí
- [x] Stripe integrace — předplatné, webhooky, usage-limits
- [x] Plugin systém — registrace custom nav položek, activity typů, webhook event typů
- [x] Automatizace — trigger/condition/action engine s Celery
- [x] Vue 3 SPA (Vite, Pinia, Vue Router, Tailwind, dark mode, i18n: cs/en/de/pl)
- [x] Docker Compose, CI/CD, Sentry, PWA, E2E testy (Playwright)

---

## Architektura systému

### I. CRM — Vztahy a Obchod

#### 1.1 Adresář
Centrální evidence subjektů — firem i osob. Všechny ostatní entity systému (Příležitosti, Realizace, Správa, Úkoly, Výkazy) se na záznamy v Adresáři váží.

**Datový model:**
- `Contact` — unifikovaný model pro fyzické osoby i firmy (typ: `person` / `company`)
- Pole: jméno, e-mail, telefon, web, adresa, IČO/DIČ, tagy, vlastní metadata
- Vztahy: kontakt může být zaměstnancem/kontaktní osobou jiné firmy

**Funkce:**
- Vyhledávání a filtrování (jméno, e-mail, telefon, IČO, tag)
- Import/export CSV
- Rychlé akce: mailto, tel, odkaz na web
- Propojení na všechny navazující entity
- Enrichment (plugin: LinkedIn, Clearbit)

---

#### 1.2 Příležitosti
Obchodní Kanban. Aktivuje se při vstupu nového obchodního podnětu. Vychází z nynějšího modulu Lead.

**Datový model:**
- Pole: název, hodnota, měna, zdroj, fáze, přiřazená osoba, termín uzavření, popis
- Vazby: Adresář (kontakt/firma), Úkoly, Aktivity, Nabídky, Dokumenty, Realizace (1:1 po vyhraní)

**Pipeline fáze:** Nový → Kontaktovaný → Kvalifikovaný → Nabídka → Vyhráno / Prohráno / Zrušeno

**Funkce:**
- Kanban board (drag-and-drop) + tabulkový pohled
- Inline editace stavu, hodnoty a přiřazení
- Lead scoring (0–100) dle konfigurovatelných pravidel
- Uložené pohledy (filtry + řazení)
- Automatické vytvoření Realizace při přechodu na „Vyhráno"

---

#### 1.3 Realizace *(nová entita)*
Výrobní / servisní Kanban. Aktivuje se automaticky po vyhrané Příležitosti. Řeší doručení hodnoty zákazníkovi.

**Datový model:**
- Vazba 1:1 na Příležitost (origin), N:1 na Adresář (zákazník)
- Pole: název, fáze, odpovědná osoba, termín zahájení, termín dokončení, popis
- Komponenty: Úkoly, Aktivity, Dokumenty, Výkazy (náklady/výnosy), Milníky

**Pipeline fáze:** Naplánováno → Probíhá → Pozastaveno → Dokončeno / Zrušeno

**Funkce:**
- Kanban board pro Realizace (stejný UI pattern jako Příležitosti)
- Milníky s vazbou na Kalendář
- Měření času na úrovni celé Realizace i jednotlivých Úkolů
- Generování fakturačních podkladů do Výkazů

---

#### 1.4 Správa *(nová entita)*
Post-realizační fáze. Péče o zákazníka, SLA, záruky a retence.

**Datový model:**
- Vazba na Realizaci (origin) a Adresář (zákazník)
- Pole: typ (SLA / Záruka / Retence / Péče), stav, odpovědná osoba, termín expirace, poznámky
- Komponenty: Úkoly (service kanban), Aktivity, Dokumenty, Výkazy

**Pipeline fáze (Service Kanban):** Otevřeno → Řeší se → Čeká na zákazníka → Uzavřeno

**Funkce:**
- SLA tracking — výpočet zbývajícího času, barevné indikátory
- Automatická eskalace (Automatizace engine)
- Propojení zpětné vazby s Příležitostmi (upsell/cross-sell)

---

### II. ERP — Provoz a Nástroje

#### 2.1 Úkoly
Rozšíření stávajícího globálního Task Manageru.

**Funkce:**
- Úkol může být zcela samostatný nebo volitelně propojený s libovolnou CRM entitou (Adresář / Příležitost / Realizace / Správa)
- Šablony úkolů, opakování, kontrolní seznamy (checklisty)
- Přiřazení více členům týmu, sledování stavu

---

#### 2.2 Měření času *(nová funkce)*
Sitewide časovač přístupný z libovolné části aplikace.

**Funkce:**
- Plovoucí počítadlo (persistent UI widget) viditelné po celou dobu prohlížení aplikace
- Spuštění s výběrem kontextu: ke které entitě se čas váže (Úkol / Příležitost / Realizace / Správa / Adresář nebo samostatně)
- Více záznamů na stejnou entitu od různých členů týmu
- Ruční zadání záznamu (zpětně)
- Export do Výkazů (timesheet)

---

#### 2.3 Kalendář
Agregované zobrazení termínů ze všech CRM entit.

**Funkce:**
- Měsíční / týdenní / denní pohled (FullCalendar)
- Zdroje: Úkoly (due date), Milníky Realizací, SLA expiry (Správa), Události aktivit
- Inline vytváření úkolů kliknutím na datum
- iCal export

---

#### 2.4 Výkazy *(rozšíření)*
Finanční mezivrstva — sběr nákladů a výnosů z celého systému.

**Datový model:**
- `TimeEntry` — záznam z časovače (viz 2.2); vazba na libovolnou entitu
- `ExpenseItem` — jednorázová nebo opakovaná nákladová položka; vazba na libovolnou entitu
- `RevenueItem` — jednorázová nebo opakovaná výnosová položka (např. schválená nabídka, milník Realizace)
- Agregace po Firmě / Projektu / Zákazníkovi / Datu

**Funkce:**
- Timesheet — přehled odpracovaného času (filtrovatelný po členu týmu, entitě, datu)
- Přehled nákladů a výnosů (P&L na úrovni Příležitosti / Realizace / Zákazníka)
- Položkový rozpad ziskovosti
- Integrace Fakturoid API — tvorba nabídek a faktur přímo z Výkazů
- Export do CSV / PDF

---

#### 2.5 Dokumenty *(nová entita)*
Centrální správa souborů s vazbou na entity.

**Funkce:**
- Upload souborů (drag-and-drop, XHR progress)
- Vazba na libovolnou CRM entitu (Adresář / Příležitost / Realizace / Správa)
- Sdílení pomocí podepsaného dočasného odkazu
- Preview obrázků a PDF přímo v aplikaci
- Vyhledávání napříč dokumenty (název, typ, entita)

---

### III. INSIGHT — Data a Mozek

#### 3.1 Statistiky
Reporting výkonu obchodu, týmu a pipeline.

**Funkce:**
- Pipeline velocity (průměrný čas ve fázi)
- Vyhráno / Prohráno dle zdroje (stacked bar)
- Výkon týmu (Příležitosti, Realizace, Úkoly, odpracovaný čas)
- Marže a ziskovost (z Výkazů)
- Trendy: nové/uzavřené Příležitosti a Realizace za 12 týdnů
- Konfigurovatelný date range picker

---

#### 3.2 Automatizace
Engine pro workflow — bez nutnosti kódu.

**Triggery:**
- Změna stavu libovolné CRM entity (Příležitosti, Realizace, Správy, Úkolu)
- Vypršení SLA / záruky (Správa)
- Nový záznam v Adresáři
- Příchozí webhook

**Akce:**
- Vytvořit Realizaci při vyhraní Příležitosti
- Vytvořit úkol / eskalovat SLA
- Odeslat e-mail / Slack notifikaci
- Aktualizovat pole / přiřadit osobu
- Spustit plugin

---

### IV. Nastavení

- **Správa týmu** — pozvánky, role, oprávnění
- **Pluginy** — manager instalovaných pluginů, konfigurace, sandbox
- **Systémové nastavení** — profil, workspace, Stripe, API tokeny, webhooky, šablony nabídek, pipeline fáze
- **Super Admin zóna** — přehled všech firem, ruční úpravy předplatného

---

## Fázovaná Roadmapa

### Fáze 4.0 — Měření času a Výkazy

Sitewide časovač a finanční mezivrstva.

- [x] **TimeEntry model** — nový Django model se vazbou na volitelnou entitu (GenericForeignKey nebo nullable FK na Lead/Customer/…)
- [x] **REST API pro TimeEntry** — CRUD (`/api/v1/erp/time-entries`), filtry po uživateli, entitě, datu
- [x] **Sitewide časovač** — Vue 3 composable `useTimer` (start/stop/reset); stav persistován v Pinia; plovoucí UI widget v AppShell (viditelný přes router-view)
- [x] **Výběr kontextu** — modal/popover při spuštění časovače: vybrat typ entity + konkrétní záznam (search dropdown); lze spustit bez kontextu
- [x] **Manuální zadání záznamu** — formulář pro ruční timesheet záznam s výběrem entity
- [x] **Timesheet view** — nová stránka `/app/timesheets`; tabulka záznamů s filtry; inline editace a mazání
- [x] **ExpenseItem a RevenueItem modely** — jednorázové i opakované položky s vazbou na entitu
- [x] **Výkazy view** — `/app/reports`; P&L přehled, položkový rozpad, exporty CSV/PDF
- [ ] **Fakturoid integrace** — API klíč v Nastavení; tvorba nabídek/faktur z agregovaných dat Výkazů
- [x] Navigace — přidat „Výkazy" a „Čas" do ERP sekce sidebaru
- [ ] Testy — Vitest pro `useTimer`, Pinia store; Django testy pro nová API

---

### Fáze 4.1 — Realizace

Výrobní Kanban aktivovaný po vyhraní Příležitosti.

- [x] **Realization model** — Django model s vazbou na `Lead` (origin, nullable), `Customer`, přiřazenou osobou, fázemi a milníky
- [x] **Milestone model** — milníky Realizace (název, datum, splněno T/F); vazba na Kalendář
- [x] **REST API** — CRUD pro Realizace a Milníky (`/api/v1/crm/realizations`, `/milestones`)
- [x] **Automatizace trigger** — „Při Won v Příležitosti → vytvořit Realizaci" jako built-in automation template
- [x] **Realizace view** — `/app/realizations`; Kanban board (stejný pattern jako Příležitosti); drag-and-drop fáze
- [x] **Detail Realizace** — záložky: Přehled / Úkoly / Aktivity / Dokumenty / Výkazy / Milníky
- [x] **Měření času** — rozšíření `useTimer` o kontext Realizace
- [x] **Navigace** — přidat „Realizace" do CRM sekce sidebaru; aktualizovat i18n (cs/en/de/pl)
- [x] WebSocket eventy — `realization.created/updated/deleted`
- [ ] Testy — Django + Vitest + Playwright smoke test

---

### Fáze 4.2 — Správa

Post-realizační fáze (SLA, záruky, retence).

- [x] **Management model** — Django model s vazbou na `Realization` (origin), `Customer`, typem (SLA/Záruka/Retence/Péče), stavem a termínem expirace
- [x] **REST API** — CRUD (`/api/v1/crm/management`)
- [x] **SLA tracking** — výpočet zbývajícího času; barevné indikátory (zelená/žlutá/červená)
- [ ] **Automatizace** — trigger „SLA expiruje za N dní → eskaluj / pošli notifikaci"
- [x] **Service Kanban view** — `/app/management`; 4-stavový kanban
- [x] **Detail Správy** — záložky: Přehled / Úkoly / Aktivity
- [x] **Navigace** — přidat „Správa" do CRM sekce sidebaru; aktualizovat i18n
- [ ] Testy

---

### Fáze 4.3 — Dokumenty

Centrální správa souborů.

- [x] **Document model** — nullable FKs na libovolnou entitu; pole: název, typ, velikost, URL, nahráno kým/kdy
- [x] **REST API** — upload, list, delete (`/api/v1/erp/documents`)
- [x] **Documents view** — `/app/documents`; tabulka s filtry a vyhledáváním
- [x] **Integrace do Detail views** — záložka Dokumenty v Realizaci a Správě
- [ ] Vyhledávání dokumentů v Command Palette
- [ ] Testy

---

### Fáze 4.4 — Adresář v2 (Firmy a Lidé)

Rozšíření stávajícího Customer modelu na plnohodnotný Adresář.

- [ ] **Unifikovaný Contact model** — přidat `type` pole (`person` / `company`); přidat pole IČO, DIČ, adresa, web; přidat relaci „zaměstnanec firmy" (self-referential FK)
- [ ] **Migrace** — DataMigration: stávající Customer záznamy → Contact type=person (nebo company dle přítomnosti company_name)
- [ ] **Adresář view** — přidání přepínače Firmy / Lidé; zobrazení hierarchie (firma → kontaktní osoby)
- [ ] **Detail kontaktu** — záložky: Info / Příležitosti / Realizace / Správa / Úkoly / Dokumenty / Aktivity
- [ ] **Enrichment plugin** — LinkedIn/Clearbit napojení (dobrovolné)
- [ ] Testy

---

### Fáze 4.5 — Statistiky v2

Rozšíření analytického modulu o nové entity.

- [ ] Přidat metriky Realizací do pipeline reportů
- [ ] Výkonnostní report: čas → ziskovost (z Výkazů + Realizací)
- [ ] Přehled SLA plnění (Správa)
- [ ] Konfigurovatelný dashboard — drag-and-drop widget layout (vue-grid-layout), uložení per-user
- [ ] Plánované reporty — týdenní e-mailový digest (Celery beat)

---

### Fáze 4.6 — Automatizace v2

Rozšíření automation engine o nové triggery a akce.

- [ ] Nové triggery: změna fáze Realizace, SLA expiry, nový kontakt v Adresáři, dokončení Milníku
- [ ] Nové akce: vytvoření Správy po dokončení Realizace, přiřazení záznamu Adresáře, spuštění Fakturoid akce
- [ ] Výchozí automation templates pro celý CRM lifecycle (Příležitost → Realizace → Správa)
- [ ] Vizuální editor podmínek (AND/OR builder)

---

### Fáze 5.0 — Platform Release

- [ ] Audit překladu — kontrola pokrytí všech klíčů ve všech lokalizacích (cs/en/de/pl)
- [ ] Security audit — externí penetrační test; vyřešení všech kritických nálezů
- [ ] SLA & uptime — public status page; PagerDuty alerting
- [ ] Aktualizace marketingové stránky a dokumentace (MkDocs) o nové funkce
- [ ] Demo data — seed script pro celý CRM lifecycle (Adresář → Příležitost → Realizace → Správa)
- [ ] Veřejné oznámení a changelog

---

## Principy architektury (zachovány z v1–v3)

1. **Multi-tenancy first** — veškerá data jsou striktně scopována na Firm; žádný únik dat mezi nájemníky
2. **Explicit over implicit** — kontroly oprávnění (`require_membership`, `require_active_subscription`) jsou volány na vrcholu každého endpointu
3. **Thin models, fat API** — business logika žije v API vrstvě (transakce, side-efekty, Celery dispatch)
4. **Graceful degradation** — volitelné služby (Celery, Redis, S3, Stripe, Fakturoid) nezpůsobují hard failure při absenci konfigurace
5. **API-first** — Django Ninja / OpenAPI jako primární interface; Vue SPA je konzumentem stejného API

# Re-Goals: LeadLab Feature Audit & Fix List

Tato analýza popisuje aktuální stav implementace a seznam věcí, které je třeba opravit nebo dokončit, aby všechny integrované funkce byly viditelné a funkční i pro přihlášeného superadmina.

---

## Kořenová příčina problému

Projekt má **dvě oddělená frontendová rozhraní**:

| URL prefix | Technologie | Stav |
|---|---|---|
| `/dashboard/*` | Django šablony + vanilla JS (v1.1) | Starý frontend, omezenéfunkce |
| `/app/*` | Vue 3 SPA (v1.2–v2.5) | Nový frontend, plné funkce |

Přihlašovací stránka Django (`/login/`) přesměruje po úspěšném přihlášení na `/dashboard/`, který je starý a postrádá většinu nových funkcí (cmd zkratky, Billing, @mention, Proposals, Templates, Plugin marketplace, Automations, Analytics, SuperAdmin panel, atd.).

**Všechny nové funkce jsou dostupné na `/app/dashboard` (Vue SPA), nikoliv na `/dashboard/`.** Základní fix je buď přesměrovat uživatele po přihlášení na `/app/`, nebo jasně zobrazit odkaz na nový frontend.

---

## Kategorie oprav

### 🔴 KRITICKÉ — Uživatel nevidí nové funkce

#### 1. Login přesměrování na starý `/dashboard/` místo `/app/dashboard`
- **Soubor:** `frontend/views.py` (nebo šablona `login.html`)
- **Problém:** Po přihlášení skrz `/login/` je uživatel přesměrován na `/dashboard/` (vanilla JS frontend z v1.1), který nemá cmd zkratky, proposals, analytics, plugins, automations, billing apod.
- **Fix:** Změnit redirect po úspěšném přihlášení na `/app/dashboard` místo `/dashboard/`. Zvážit zachování `/dashboard/` jako deprecated zálohy.

#### 2. Navigace v AppShell nezobrazuje všechny sekce
- **Soubor:** `frontend-spa/src/views/AppShell.vue` (navItems)
- **Problém:** Navigace v bočním panelu má pouze: Dashboard, Leads, Customers, Calendar, Team, Analytics, Settings (+ SuperAdmin pro staff). Chybí přímé links na: Proposals, Automations, Plugin Marketplace.
- **Fix:** Proposals jsou dostupné pouze přes detail Leadu — zvážit, zda přidat samostatnou položku `/app/proposals` v navigaci. Automations a Plugins jsou pohřbeny v Settings — zvážit viditelný odkaz nebo badge.

#### 3. Billing sekce chybí v Settings
- **Soubor:** `frontend-spa/src/views/SettingsView.vue`
- **Problém:** SettingsView zobrazuje pouze: Profile, Workspace, Danger Zone, API Tokens, Webhooks, Notifications, Branding (Pro gate), Language, Lead Scoring, Proposal Templates, Plugins, Automations. **Chybí Billing sekce** s tlačítkem "Upgrade to Pro" / "Manage subscription", i když backend endpoint `/api/v1/firms/{id}/billing/checkout` existuje a je funkční.
- **Fix:** Přidat sekci "Billing" do SettingsView se zobrazením aktuálního subscription tieru, tlačítkem "Upgrade to Pro" (volá `/api/v1/firms/{id}/billing/checkout` a přesměruje na Stripe), a stavem aktivity předplatného.

---

### 🟠 DŮLEŽITÉ — Funkce existují, ale jsou špatně zapojené nebo viditelné

#### 4. Keyboard shortcuts (cmd zkratky) nefungují na starém `/dashboard/`
- **Soubor:** `frontend-spa/src/composables/useKeyboardShortcuts.ts`, `AppShell.vue`
- **Problém:** `useKeyboardShortcuts` je wired pouze v AppShell (Vue SPA). Na starém `/dashboard/` chybí úplně.
- **Fix:** Po vyřešení bodu 1 (redirect na `/app/`) se tento problém vyřeší automaticky. Zkratky jsou implementovány správně: `Cmd/Ctrl+K` (command palette), `G L`, `G C`, `G D`, `N`, `?`.

#### 5. @mention v textareas nefunguje na starém `/dashboard/`
- **Soubor:** `frontend-spa/src/components/RichTextEditor.vue`
- **Problém:** `RichTextEditor` s Tiptap a @mention je dostupný pouze v Activity timeline na Lead Detail Viewu ve Vue SPA (`/app/leads/:id`). Starý frontend používá prosté `<textarea>` bez mention funkcionality.
- **Fix:** Opět vyřeší redirect na `/app/`. Tiptap + @mention je plně implementovaný.

#### 6. Proposals nejsou dostupné jako samostatná sekce
- **Soubor:** Router (`frontend-spa/src/router/index.ts`), AppShell navigace
- **Problém:** Proposals jsou dostupné pouze přes URL `/app/leads/:id/proposals/:pid` (z Lead detail stránky). Neexistuje globální přehled návrhů přes celou firmu.
- **Fix (krátkodobý):** Přidat tlačítko "New Proposal" nebo "View Proposals" přímo na Lead Detail stránku s jasným CTA. Zvážit globální `/app/proposals` seznam view pro přehled všech proposals firmy.
- **Fix (dlouhodobý):** Přidat `/app/proposals` route a view se seznamem všech proposals filtrovaných po firmě.

#### 7. Plugin Marketplace URL nefunguje
- **Soubor:** `frontend-spa/src/views/SettingsView.vue` (řádek ~1409, ~1555)
- **Problém:** Odkazuje na `https://github.com/JakubMusil/LeadLab/tree/main/docs/plugin-registry.json` a `https://github.com/JakubMusil/LeadLab/blob/main/public/plugin-registry.json` — tyto soubory pravděpodobně neexistují v repozitáři.
- **Fix:** Vytvořit `public/plugin-registry.json` v repozitáři se seznamem dostupných first-party pluginů (email_sequences, voip, linkedin_enrichment, slack_notifications). Zkontrolovat a opravit URL.

#### 8. SuperAdmin panel je skrytý za `is_staff` check
- **Soubor:** `frontend-spa/src/views/AppShell.vue` (řádek ~109)
- **Problém:** Odkaz na `/app/superadmin` se zobrazuje pouze když `authStore.user?.is_staff === true`. Pokud superadmin není označen jako `is_staff` v Django, panel není viditelný.
- **Fix:** Ověřit, zda je superadmin účet správně označen jako `is_staff` v Django admin. Případně přidat alternativní check (např. `is_superuser`).

---

### 🟡 STŘEDNÍ — Chybějící UI pro existující backend

#### 9. iCal feed — chybí UI v Settings
- **Backend:** Endpoint pro iCal export pravděpodobně existuje (dle goals.md v1.7 ✅)
- **Frontend:** Žádná sekce v SettingsView pro zkopírování iCal URL
- **Fix:** Přidat "Calendar Feed" sekci do Settings s tlačítkem pro vygenerování/zkopírování iCal URL

#### 10. CSV Import — chybí UI
- **Backend:** CSV import endpoint existuje (goals.md v1.7 ✅)
- **Frontend:** Žádný upload form pro CSV import v Leads nebo Customers view
- **Fix:** Přidat "Import CSV" tlačítko s file upload a progress panelem do LeadsView a CustomersView

#### 11. CSV/PDF Export — chybí UI nebo je nedostupný
- **Backend:** Export endpointy existují (goals.md v1.7 ✅)
- **Frontend:** Ověřit, zda jsou tlačítka "Export CSV" a "Export PDF" přítomna v LeadsView/CustomersView
- **Fix:** Přidat export tlačítka pokud chybí

#### 12. Webhook delivery log — chybí UI
- **Backend:** `WebhookEndpoint` model + API existuje
- **Frontend:** SettingsView zobrazuje seznam webhooků, ale chybí "delivery log" pro zobrazení historie doručení
- **Fix:** Přidat expandovatelnou sekci pro každý webhook endpoint s posledními 10 delivery pokusy (status, timestamp, response code)

#### 13. Automation runs log — částečně implementovaný
- **Backend:** `AutomationRun` model existuje, endpoint `/api/v1/crm/automations/{id}/runs` existuje
- **Frontend:** `toggleRuleRuns` funkce je implementována, ale ověřit zda je UI plně zobrazené v template
- **Fix:** Zkontrolovat zda se runs log správně renderuje pod každým automation pravidlem v SettingsView

#### 14. Public status stránka pro proposals — veřejné URL
- **Backend:** `/api/v1/crm/public/proposals/{token}` endpoint existuje
- **Frontend:** `PublicProposalView.vue` existuje s routou `/proposals/public/:token`
- **Status:** Vypadá implementovaně — ověřit end-to-end flow (send → vygenerovat link → zákazník vidí proposal → accept/reject)

---

### 🔵 NÍZKÁ PRIORITA — Dobré mít

#### 15. Dark mode nedosahuje na všechny komponenty
- Ověřit `dark:` Tailwind třídy na: SettingsView sekce (Proposal Templates sekce postrádá `dark:` třídy), LeadsView modály, CalendarView
- Systematicky projít každou view a doplnit chybějící `dark:` varianty

#### 16. i18n — chybějící překlady
- Soubory `locales/en.json` a `locales/cs.json` existují, ale ověřit pokrytí klíčů
- Velká část SettingsView a nových komponent (Proposals, Automations, Plugins) pravděpodobně nepoužívá `t()` a má hardcoded anglické texty
- **Fix:** Projít všechny views a nahradit hardcoded texty `t()` voláními, doplnit klíče do locale souborů

#### 17. Onboarding banner — chybí
- dle goals.md v2.0: "dashboard banner directs returning users back to onboarding until complete"
- Ověřit zda DashboardView zobrazuje onboarding progress banner pro nové workspaces

#### 18. E2E testy nepokrývají nové funkce
- Playwright testy v `e2e/` adresáři pokrývají základní flow (registration, leads)
- Chybí testy pro: proposals workflow, automation rules, plugin enable/disable, billing checkout redirect

---

## Přehled funkčního stavu (Vue SPA `/app/`)

| Funkce | Backend | Frontend | Funkční? |
|---|---|---|---|
| Login / Register / Reset password | ✅ | ✅ | ✅ |
| Onboarding (workspace creation) | ✅ | ✅ | ✅ |
| Dashboard (stats, charts, widgets) | ✅ | ✅ | ✅ |
| Leads list + Kanban board | ✅ | ✅ | ✅ |
| Lead detail (activities, tasks, files) | ✅ | ✅ | ✅ |
| Customers list + detail | ✅ | ✅ | ✅ |
| Task calendar (FullCalendar) | ✅ | ✅ | ✅ |
| Team management + invites | ✅ | ✅ | ✅ |
| Settings (profile, workspace, tokens, webhooks) | ✅ | ✅ | ✅ |
| **Billing / Stripe Checkout** | ✅ | ❌ chybí UI | ⚠️ |
| Analytics (pipeline velocity, charts) | ✅ | ✅ | ✅ |
| SuperAdmin panel | ✅ | ✅ (is_staff only) | ⚠️ |
| Keyboard shortcuts (Cmd+K, G L, etc.) | — | ✅ (pouze v SPA) | ✅ |
| Command palette | — | ✅ | ✅ |
| @mention v activity editoru (Tiptap) | ✅ | ✅ | ✅ |
| Dark mode | — | ✅ (částečné) | ⚠️ |
| **Proposals + Quote Builder** | ✅ | ✅ (přes Lead detail) | ✅ |
| **Proposal Templates** | ✅ | ✅ (v Settings) | ✅ |
| **Public proposal link (accept/reject)** | ✅ | ✅ | ✅ |
| **PDF generace proposals** | ✅ (weasyprint) | ✅ | ✅ |
| **Plugin Marketplace** | ✅ | ✅ (v Settings) | ⚠️ registry URL broken |
| **Automations** | ✅ | ✅ (v Settings) | ✅ |
| Lead scoring | ✅ | ✅ (v Settings) | ✅ |
| Saved views | ✅ | ✅ | ✅ |
| WebSocket real-time updates | ✅ | ✅ | ✅ |
| Notification bell | ✅ | ✅ | ✅ |
| JWT API tokens | ✅ | ✅ | ✅ |
| Outbound webhooks | ✅ | ✅ | ✅ |
| iCal feed | ? | ❌ chybí UI | ⚠️ |
| CSV import | ✅ | ❌ chybí UI | ⚠️ |
| CSV/PDF export | ✅ | ❌ ověřit | ⚠️ |
| Push notifications (Web Push) | ✅ | ✅ | ✅ |
| Branding (logo + color) | ✅ | ✅ (Pro only) | ✅ |
| White-label | ✅ | ✅ | ✅ |
| Multi-language (EN/CS/DE/PL) | — | ✅ (hardcoded v částech) | ⚠️ |
| Storybook component library | — | ✅ | ✅ |
| PWA manifest + service worker | — | ✅ | ✅ |
| MkDocs dokumentace | ✅ | — | ✅ |

---

## Doporučené pořadí oprav

1. **[KRITICKÉ]** Přesměrovat login na `/app/dashboard` místo `/dashboard/` → uživatelé uvidí všechny funkce okamžitě
2. **[KRITICKÉ]** Přidat Billing sekci do SettingsView (Upgrade to Pro button)
3. **[DŮLEŽITÉ]** Opravit plugin-registry.json URL v SettingsView
4. **[DŮLEŽITÉ]** Ověřit SuperAdmin is_staff nastavení pro superadmin účet
5. **[STŘEDNÍ]** Přidat iCal feed UI do Settings
6. **[STŘEDNÍ]** Přidat CSV import UI do Leads/Customers
7. **[STŘEDNÍ]** Přidat webhook delivery log UI
8. **[NÍZKÁ]** Doplnit dark mode `dark:` třídy do zbývajících sekcí
9. **[NÍZKÁ]** i18n — doplnit t() překlady do nových sekcí
10. **[NÍZKÁ]** E2E testy pro nové funkce (proposals, automations, plugins)

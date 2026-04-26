# Re-Goals: LeadLab Feature Audit & Fix List

Tato analýza popisuje aktuální stav implementace a seznam věcí, které je třeba opravit nebo dokončit, aby všechny integrované funkce byly viditelné a funkční i pro přihlášeného superadmina.

---

## Kořenová příčina problému

Projekt má **dvě oddělená frontendová rozhraní**:

| URL prefix | Technologie | Stav |
|---|---|---|
| `/dashboard/*` | Django šablony + vanilla JS (v1.1) | Odstraněno; permanentní 301 → `/app/*` |
| `/app/*` | Vue 3 SPA (v1.2–v2.5) | Nový frontend, plné funkce |

Přihlašovací stránka Django (`/login/`) přesměruje po úspěšném přihlášení na `/dashboard/`, který je starý a postrádá většinu nových funkcí (cmd zkratky, Billing, @mention, Proposals, Templates, Plugin marketplace, Automations, Analytics, SuperAdmin panel, atd.).

**Všechny nové funkce jsou dostupné na `/app/dashboard` (Vue SPA), nikoliv na `/dashboard/`.** Základní fix je buď přesměrovat uživatele po přihlášení na `/app/`, nebo jasně zobrazit odkaz na nový frontend.

---

## Kategorie oprav

### 🔴 KRITICKÉ — Uživatel nevidí nové funkce

#### 1. ~~Login přesměrování na starý `/dashboard/` místo `/app/dashboard`~~ ✅ OPRAVENO
- Staré `/dashboard/*` URL jsou odstraněny; nastaveny permanentní redirecty na `/app/dashboard`.
- Login a onboarding šablony přesměrovávají na `/app/dashboard`.

#### 2. ~~Navigace v AppShell nezobrazuje všechny sekce~~
- **Soubor:** `frontend-spa/src/views/AppShell.vue` (navItems)
- **Problém:** Navigace v bočním panelu má pouze: Dashboard, Leads, Customers, Calendar, Team, Analytics, Settings (+ SuperAdmin pro staff). Chybí přímé links na: Proposals, Automations, Plugin Marketplace.
- **Fix:** Proposals jsou dostupné pouze přes detail Leadu — zvážit, zda přidat samostatnou položku `/app/proposals` v navigaci. Automations a Plugins jsou pohřbeny v Settings — zvážit viditelný odkaz nebo badge.

#### 3. ~~Billing sekce chybí v Settings~~ ✅ OPRAVENO
- **Soubor:** `frontend-spa/src/views/SettingsView.vue`
- Přidána sekce "Billing" se zobrazením aktuálního subscription tieru, tlačítkem "Upgrade to Pro" (volá `/api/v1/firms/{id}/billing/checkout` a přesměruje na Stripe Checkout), a stavem aktivity předplatného.
- Uživatelé na Free tieru vidí seznam Pro výhod a tlačítko "Upgrade to Pro".

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

#### 7. ~~Plugin Marketplace URL nefunguje~~ ✅ OPRAVENO
- **Soubor:** `frontend-spa/src/views/SettingsView.vue`
- URL opraveny na `/plugin-registry.json` (statický soubor servovaný z `frontend-spa/public/`). Soubor existuje se 4 first-party pluginy.

#### 8. ~~SuperAdmin panel je skrytý za `is_staff` check~~ ✅ OPRAVENO
- **Soubory:** `frontend-spa/src/views/AppShell.vue`, `frontend-spa/src/stores/auth.ts`, `users/api.py`
- Přidán `is_superuser` do `UserOut` API schématu a do `/me` endpointu.
- AppShell nyní zobrazuje odkaz na `/app/superadmin` pro uživatele kde `is_staff || is_superuser`.

---

### 🟡 STŘEDNÍ — Chybějící UI pro existující backend

#### 9. ~~iCal feed — chybí UI v Settings~~ ✅ OPRAVENO
- **Frontend:** Přidána sekce "Calendar Feed" do SettingsView s tlačítkem pro generování iCal URL a tlačítkem Copy.

#### 10. ~~CSV Import — chybí UI~~ ✅ OPRAVENO
- **Frontend:** Přidáno "Import CSV" tlačítko do LeadsView a CustomersView (file input + volání `/api/v1/integrations/import/{leads|customers}`).

#### 11. ~~CSV/PDF Export — chybí UI nebo je nedostupný~~ ✅ OPRAVENO
- **Frontend:** Přidána tlačítka "⬇ CSV" a "⬇ PDF" do LeadsView; "⬇ CSV" do CustomersView (volají `/api/v1/integrations/export/`).

#### 12. ~~Webhook delivery log — chybí UI~~ ✅ OPRAVENO
- **Frontend:** Přidán expandovatelný "View log" panel pro každý webhook endpoint v SettingsView (zobrazuje event, status code, duration, timestamp).

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
| **Billing / Stripe Checkout** | ✅ | ✅ (v Settings) | ✅ |
| Analytics (pipeline velocity, charts) | ✅ | ✅ | ✅ |
| SuperAdmin panel | ✅ | ✅ (is_staff \|\| is_superuser) | ✅ |
| Keyboard shortcuts (Cmd+K, G L, etc.) | — | ✅ (pouze v SPA) | ✅ |
| Command palette | — | ✅ | ✅ |
| @mention v activity editoru (Tiptap) | ✅ | ✅ | ✅ |
| Dark mode | — | ✅ (částečné) | ⚠️ |
| **Proposals + Quote Builder** | ✅ | ✅ (přes Lead detail) | ✅ |
| **Proposal Templates** | ✅ | ✅ (v Settings) | ✅ |
| **Public proposal link (accept/reject)** | ✅ | ✅ | ✅ |
| **PDF generace proposals** | ✅ (weasyprint) | ✅ | ✅ |
| **Plugin Marketplace** | ✅ | ✅ (v Settings) | ✅ |
| **Automations** | ✅ | ✅ (v Settings) | ✅ |
| Lead scoring | ✅ | ✅ (v Settings) | ✅ |
| Saved views | ✅ | ✅ | ✅ |
| WebSocket real-time updates | ✅ | ✅ | ✅ |
| Notification bell | ✅ | ✅ | ✅ |
| JWT API tokens | ✅ | ✅ | ✅ |
| Outbound webhooks | ✅ | ✅ | ✅ |
| iCal feed | ✅ | ✅ (v Settings) | ✅ |
| CSV import | ✅ | ✅ (Leads + Customers) | ✅ |
| CSV/PDF export | ✅ | ✅ (Leads + Customers) | ✅ |
| Push notifications (Web Push) | ✅ | ✅ | ✅ |
| Branding (logo + color) | ✅ | ✅ (Pro only) | ✅ |
| White-label | ✅ | ✅ | ✅ |
| Multi-language (EN/CS/DE/PL) | — | ✅ (hardcoded v částech) | ⚠️ |
| Storybook component library | — | ✅ | ✅ |
| PWA manifest + service worker | — | ✅ | ✅ |
| MkDocs dokumentace | ✅ | — | ✅ |

---

## Doporučené pořadí oprav

1. ~~**[KRITICKÉ]** Přesměrovat login na `/app/dashboard` místo `/dashboard/` → uživatelé uvidí všechny funkce okamžitě~~ ✅ HOTOVO (staré `/dashboard/*` odstraněny, permanentní redirecty nastaveny)
2. ~~**[KRITICKÉ]** Přidat Billing sekci do SettingsView (Upgrade to Pro button)~~ ✅ HOTOVO
3. ~~**[DŮLEŽITÉ]** Opravit plugin-registry.json URL v SettingsView~~ ✅ HOTOVO
4. ~~**[DŮLEŽITÉ]** Ověřit SuperAdmin is_staff nastavení; přidat is_superuser alternativu~~ ✅ HOTOVO
5. ~~**[STŘEDNÍ]** Přidat iCal feed UI do Settings~~ ✅ HOTOVO
6. ~~**[STŘEDNÍ]** Přidat CSV import UI do Leads/Customers~~ ✅ HOTOVO
7. ~~**[STŘEDNÍ]** Přidat webhook delivery log UI~~ ✅ HOTOVO
8. **[NÍZKÁ]** Doplnit dark mode `dark:` třídy do zbývajících sekcí
9. **[NÍZKÁ]** i18n — doplnit t() překlady do nových sekcí
10. **[NÍZKÁ]** E2E testy pro nové funkce (proposals, automations, plugins)

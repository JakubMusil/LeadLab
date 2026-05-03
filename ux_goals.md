# UX/UI Goals & Backlog

Tento dokument shrnuje identifikované UX a UI nedostatky a náměty na zlepšení vycházející z analýzy zdrojového kódu. Položky jsou seřazeny podle priority.

---

## 🔴 Prioritní (konzistence / chyby)

### 1. Dashboard stále používá `useLeadsStore` (starý store) ✅ HOTOVO
- **Soubor:** `frontend-spa/src/views/DashboardView.vue`
- **Popis:** DashboardView importuje `useLeadsStore` a `LeadOut` — zatímco zbytek aplikace byl migrován na `useRecordsStore`. Widgety „My Top Leads", grafy i rychlé vytvoření záznamu pracují se starými daty. Widget label je `dashboard.quickCreateLead` místo pipeline-aware varianty.
- **Cíl:** Migrovat DashboardView na `useRecordsStore`, sjednotit s aktuální pipeline architekturou.

### 2. RecordDetailView — dva paralelní systémy stavů ✅ HOTOVO
- **Soubor:** `frontend-spa/src/views/RecordDetailView.vue`
- **Popis:** Stránka detailu záznamu zobrazuje zároveň stage changer (pipeline stages) i starý status progressbar (`displayedStatuses` = hardcodovaný enum new/contacted/proposal/…). Uživatel vidí obojí současně, což je matoucí.
- **Cíl:** Stage-based progressbar by měl starý status progressbar nahradit, nikoli doplnit.

### 3. RecordsView — `filterStageId` se nepromítá do URL ✅ HOTOVO
- **Soubor:** `frontend-spa/src/views/RecordsView.vue`
- **Popis:** `filterStageId` není ukládán do query parametrů URL (na rozdíl od `category_id` a `status`). Po refreshi nebo sdílení odkazu se stav filtru ztratí.
- **Cíl:** Synchronizovat `filterStageId` s URL query parametry stejně jako ostatní filtry.

---

## 🟠 Důležité (UX friction)

### 4. PipelineSettingsView — chybí drag-and-drop řazení stages ✅ HOTOVO
- **Soubor:** `frontend-spa/src/views/PipelineSettingsView.vue`
- **Popis:** Pořadí stages lze měnit pouze editací číselného pole `order`. Projekt již obsahuje závislost `VueDraggable` (používá ji `DashboardView`).
- **Cíl:** Přidat drag-and-drop handle na řádky stages pomocí existující `VueDraggable` komponenty.
- **Implementace:** Přidán `<VueDraggable>` wrapper pro seznam stages s `Bars3Icon` handle. Po přetažení se automaticky odešlou PATCH requesty pro aktualizaci `order` všech stages.

### 5. RecordDetailView — Tasks endpoint ignoruje `record_id` ✅ HOTOVO
- **Soubor:** `frontend-spa/src/views/RecordDetailView.vue` → `loadTasks()`
- **Popis:** Funkce `loadTasks()` volala `/api/v1/crm/tasks?page_size=100` a filtrovala výsledky client-side. Nyní filtruje server-side pomocí `lead_id` parametru.
- **Cíl:** ✅ Přidán `lead_id` jako query parametr do API volání.

### 6. Kanban sloupce — chybí empty state ✅ HOTOVO
- **Soubor:** `frontend-spa/src/views/RecordsView.vue` (kanban view)
- **Popis:** Stage-based kanban prázdné sloupce nyní zobrazují text „Žádné záznamy v této fázi" místo pouhé pomlčky.
- **Cíl:** ✅ Přidán placeholder do prázdných stage-based kanban sloupců.

### 7. AppShell — navigace kategorií bez počtu záznamů ✅ HOTOVO
- **Soubor:** `frontend-spa/src/views/AppShell.vue`
- **Popis:** Dynamická navigace kategorií zobrazuje barevné puntíky, ale ne počet záznamů per kategorie. Badge s počtem by výrazně zlepšil orientaci.
- **Cíl:** Zobrazit badge s počtem aktivních záznamů u každé kategorie v postranním menu.
- **Implementace:** Přidán backend endpoint `GET /api/v1/crm/records/counts-by-category` vracející `{category_id: count}` pro aktivní záznamy (bez won/lost/canceled). AppShell načítá tato data při mountu a aktualizuje je po vytvoření/smazání záznamu. Badge se zobrazuje vedle názvu kategorie se stejnou barvou jako kategorie.

---

## 🟡 Střední priorita (kvalita UX)

### 8. EntitySidebarActionPicker — mrtvý kód (modal vs. inline form) ✅ HOTOVO
- **Soubor:** `frontend-spa/src/components/EntitySidebarActionPicker.vue`
- **Popis:** Komponenta obsahuje zároveň inline form (`openInlineForm()`) i `StreamlineCreateModal` (`openModal()`). Kliknutí spouští `openInlineForm()`, takže modal se nikdy neotevře — je to mrtvý kód.
- **Cíl:** Buď modal ze šablony odstranit, nebo ho explicitně využívat pro specifické akce (voice memo, file upload) a inline formu nechat jen pro textové akce.
- **Implementace:** Odstraněn import `StreamlineCreateModal`, ref `modalOpen`/`modalActionType`, funkce `openModal()` a blok `<StreamlineCreateModal>` ze šablony.

### 9. RecordsView — create record vždy otevírá celý dialog ✅ HOTOVO
- **Soubor:** `frontend-spa/src/views/RecordsView.vue`
- **Popis:** Rychlé vytvoření záznamu vždy otevírá modální dialog s ~15 políčky. DashboardView již má jednodušší inline `qcTitle` widget.
- **Cíl:** Přidat inline quick-create variantu přímo v hlavičce stránky pro nejčastější případy.
- **Implementace:** Přidán `qcTitle` input přímo v hlavičce stránky nad pokročilými filtry. Stisk Enter nebo kliknutí na „Přidat" vytvoří záznam s title a případně s `category_id` (pokud je aktivní filtr). Přidány i18n klíče ve všech 4 jazycích.

### 10. Checkpoints vs. Tasks — vizuální nerozlišitelnost ✅ HOTOVO
- **Soubor:** `frontend-spa/src/views/RecordDetailView.vue`
- **Popis:** Checkpoints (pipeline milníky) a Tasks jsou vizuálně velmi podobné. Checkpoints jsou milníky, ne úkoly — zaslouží odlišný vizuální styl.
- **Cíl:** Odlišit checkpoints od tasks (jiná ikona, barva, layout).
- **Implementace:** Checkpoints panel nyní používá fialovou/violet barvu místo zelené, `FlagIcon` místo checkbox, kulatý styl checkboxu (místo čtvercového), fialový border sekce a kurzíva u prázdného stavu.

### 11. EntitySidebarActionPicker inline form — chybí validace a feedback ✅ HOTOVO
- **Soubor:** `frontend-spa/src/components/EntitySidebarActionPicker.vue`
- **Popis:** Přidány toast notifikace `success`/`error` po odeslání inline formu `addActivity()`.
- **Cíl:** ✅ Přidán toast feedback (success/error) po odeslání.

---

## 🟢 Nízká priorita / polishing

### 12. RecordDetailView — chybí breadcrumb navigace ✅ HOTOVO
- **Soubor:** `frontend-spa/src/views/RecordDetailView.vue`
- **Popis:** Stránka detailu záznamu nemá breadcrumb zpět do `RecordsView` (ani do správné kategorie). Jediná možnost návratu je tlačítko zpět v prohlížeči.
- **Cíl:** Přidat breadcrumb lištu: Kategorie → Název záznamu.
- **Implementace:** Přidán `<nav>` breadcrumb: „Příležitosti" → [barevný puntík + název kategorie] → [název záznamu]. Odkaz na kategorii filtruje `RecordsView` přes `?category_id=`. Kategorie se načítá z `pipelineStore` přes `currentCategory` computed property.

### 13. PipelineSettingsView — `isAdminOrOwner` vždy `true` ✅ HOTOVO
- **Soubor:** `frontend-spa/src/views/PipelineSettingsView.vue`
- **Popis:** `isAdminOrOwner` bylo implementováno jako `!!firmStore.activeFirm`. Nyní používá skutečnou roli z API (`/api/v1/firms/{id}/members`).
- **Cíl:** ✅ Implementována skutečná role-based kontrola.

### 15. RecordsView — „Smazat filtry" neresetuje pipeline filtry ✅ HOTOVO
- **Soubor:** `frontend-spa/src/views/RecordsView.vue`
- **Popis:** `clearAdvancedFilters()` nyní resetuje i `filterCategoryId` a `filterStageId` a aktualizuje URL.
- **Cíl:** ✅ Globální „Smazat filtry" resetuje všechny aktivní filtry včetně pipeline filtrů.

---

## Legenda priorit

| Symbol | Priorita | Popis |
|--------|----------|-------|
| 🔴 | Prioritní | Chyby konzistence, zavádějící UX |
| 🟠 | Důležité | Výrazný UX friction, zbytečná práce uživatele |
| 🟡 | Střední | Zlepšení kvality UX, zpětná vazba |
| 🟢 | Nízká | Polishing, edge cases |

---

## 📋 Průběh práce

### Iterace 1 (branch: `copilot/continue-work-ux-md`)

**Co bylo uděláno:**
- ✅ **#1** Dashboard migrován z `useLeadsStore`/`LeadOut` na `useRecordsStore`/`RecordOut`. API volání změněna z `/api/v1/crm/opportunities` na `/api/v1/crm/records`. Linky opraveny (`/app/opportunities/` → `/app/records/`).
- ✅ **#2** RecordDetailView — progressbar: opravena podmínka `v-if`, aby se status-based progressbar nikdy nezobrazoval, pokud záznam má nastavenou `category_id` (i když se stages teprve načítají). Přidán skeleton loader.
- ✅ **#3** RecordsView — `filterStageId` a `filterCategoryId` nyní synchronizovány s URL (inicializace z query, click handlery využívají `router.replace`). Přidán watcher pro `route.query.stage_id`.
- ✅ **#5** RecordDetailView `loadTasks()` — přidán `lead_id` parametr do API volání (server-side filter místo client-side).
- ✅ **#6** Kanban empty state — stage-based sloupce nyní zobrazují „Žádné záznamy v této fázi" místo pouhé pomlčky.
- ✅ **#11** EntitySidebarActionPicker — přidány toast notifikace (success/error) po odeslání aktivity.
- ✅ **#13** PipelineSettingsView — `isAdminOrOwner` nyní používá skutečnou roli z API (přes `/api/v1/firms/{id}/members`).
- ✅ **#15** RecordsView `clearAdvancedFilters()` — nyní resetuje i `filterCategoryId`, `filterStageId` a aktualizuje URL.

**Co zbývá:**
- **#14** Dark mode — CSS custom properties pro barvy v grafech a badges

### Iterace 2 (branch: `copilot/continue-work-on-ux-goals`)

**Co bylo uděláno:**
- ✅ **#4** PipelineSettingsView — drag-and-drop řazení stages: přidán `VueDraggable` wrapper s `Bars3Icon` drag handle, automatické PATCH requesty po přetažení.
- ✅ **#7** AppShell — badge s počtem záznamů: nový backend endpoint `GET /api/v1/crm/records/counts-by-category`, badge zobrazeny v postranním menu u každé kategorie.
- ✅ **#8** EntitySidebarActionPicker — odstraněn `StreamlineCreateModal` (mrtvý kód), `modalOpen`/`modalActionType` refs a `openModal()` funkce.
- ✅ **#9** RecordsView — inline quick-create: přidán `qcTitle` input v hlavičce s `Enter` podporou a i18n ve všech 4 jazycích.
- ✅ **#10** Checkpoints — vizuální odlišení: fialová barva, `FlagIcon`, kulatý checkbox.
- ✅ **#12** RecordDetailView — breadcrumb navigace: „Záznamy → [Kategorie] → [Název]".

**Co zbývá:**
- **#14** Dark mode — CSS custom properties pro barvy v grafech a badges

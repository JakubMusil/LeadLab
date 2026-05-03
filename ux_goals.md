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

### 4. PipelineSettingsView — chybí drag-and-drop řazení stages
- **Soubor:** `frontend-spa/src/views/PipelineSettingsView.vue`
- **Popis:** Pořadí stages lze měnit pouze editací číselného pole `order`. Projekt již obsahuje závislost `VueDraggable` (používá ji `DashboardView`).
- **Cíl:** Přidat drag-and-drop handle na řádky stages pomocí existující `VueDraggable` komponenty.

### 5. RecordDetailView — Tasks endpoint ignoruje `record_id` ✅ HOTOVO
- **Soubor:** `frontend-spa/src/views/RecordDetailView.vue` → `loadTasks()`
- **Popis:** Funkce `loadTasks()` volala `/api/v1/crm/tasks?page_size=100` a filtrovala výsledky client-side. Nyní filtruje server-side pomocí `lead_id` parametru.
- **Cíl:** ✅ Přidán `lead_id` jako query parametr do API volání.

### 6. Kanban sloupce — chybí empty state ✅ HOTOVO
- **Soubor:** `frontend-spa/src/views/RecordsView.vue` (kanban view)
- **Popis:** Stage-based kanban prázdné sloupce nyní zobrazují text „Žádné záznamy v této fázi" místo pouhé pomlčky.
- **Cíl:** ✅ Přidán placeholder do prázdných stage-based kanban sloupců.

### 7. AppShell — navigace kategorií bez počtu záznamů
- **Soubor:** `frontend-spa/src/views/AppShell.vue`
- **Popis:** Dynamická navigace kategorií zobrazuje barevné puntíky, ale ne počet záznamů per kategorie. Badge s počtem by výrazně zlepšil orientaci.
- **Cíl:** Zobrazit badge s počtem aktivních záznamů u každé kategorie v postranním menu.

---

## 🟡 Střední priorita (kvalita UX)

### 8. EntitySidebarActionPicker — mrtvý kód (modal vs. inline form)
- **Soubor:** `frontend-spa/src/components/EntitySidebarActionPicker.vue`
- **Popis:** Komponenta obsahuje zároveň inline form (`openInlineForm()`) i `StreamlineCreateModal` (`openModal()`). Kliknutí spouští `openInlineForm()`, takže modal se nikdy neotevře — je to mrtvý kód.
- **Cíl:** Buď modal ze šablony odstranit, nebo ho explicitně využívat pro specifické akce (voice memo, file upload) a inline formu nechat jen pro textové akce.

### 9. RecordsView — create record vždy otevírá celý dialog
- **Soubor:** `frontend-spa/src/views/RecordsView.vue`
- **Popis:** Rychlé vytvoření záznamu vždy otevírá modální dialog s ~15 políčky. DashboardView již má jednodušší inline `qcTitle` widget.
- **Cíl:** Přidat inline quick-create variantu přímo v hlavičce stránky pro nejčastější případy.

### 10. Checkpoints vs. Tasks — vizuální nerozlišitelnost
- **Soubor:** `frontend-spa/src/views/RecordDetailView.vue`
- **Popis:** Checkpoints (pipeline milníky) a Tasks jsou vizuálně velmi podobné. Checkpoints jsou milníky, ne úkoly — zaslouží odlišný vizuální styl.
- **Cíl:** Odlišit checkpoints od tasks (jiná ikona, barva, layout).

### 11. EntitySidebarActionPicker inline form — chybí validace a feedback ✅ HOTOVO
- **Soubor:** `frontend-spa/src/components/EntitySidebarActionPicker.vue`
- **Popis:** Přidány toast notifikace `success`/`error` po odeslání inline formu `addActivity()`.
- **Cíl:** ✅ Přidán toast feedback (success/error) po odeslání.

---

## 🟢 Nízká priorita / polishing

### 12. RecordDetailView — chybí breadcrumb navigace
- **Soubor:** `frontend-spa/src/views/RecordDetailView.vue`
- **Popis:** Stránka detailu záznamu nemá breadcrumb zpět do `RecordsView` (ani do správné kategorie). Jediná možnost návratu je tlačítko zpět v prohlížeči.
- **Cíl:** Přidat breadcrumb lištu: Kategorie → Název záznamu.

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
- **#4** PipelineSettingsView — drag-and-drop řazení stages (VueDraggable už je v projektu)
- **#7** AppShell — badge s počtem aktivních záznamů u kategorií
- **#8** EntitySidebarActionPicker — odstranění mrtvého kódu (modal vs. inline form)
- **#9** RecordsView — inline quick-create varianta v hlavičce
- **#10** Checkpoints vs. Tasks — vizuální odlišení (ikona, barva)
- **#12** RecordDetailView — breadcrumb navigace
- **#14** Dark mode — CSS custom properties pro barvy v grafech a badges

# UX/UI Goals & Backlog

Tento dokument shrnuje identifikované UX a UI nedostatky a náměty na zlepšení vycházející z analýzy zdrojového kódu. Položky jsou seřazeny podle priority.

---

## 🔴 Prioritní (konzistence / chyby)

### 1. Dashboard stále používá `useLeadsStore` (starý store)
- **Soubor:** `frontend-spa/src/views/DashboardView.vue`
- **Popis:** DashboardView importuje `useLeadsStore` a `LeadOut` — zatímco zbytek aplikace byl migrován na `useRecordsStore`. Widgety „My Top Leads", grafy i rychlé vytvoření záznamu pracují se starými daty. Widget label je `dashboard.quickCreateLead` místo pipeline-aware varianty.
- **Cíl:** Migrovat DashboardView na `useRecordsStore`, sjednotit s aktuální pipeline architekturou.

### 2. RecordDetailView — dva paralelní systémy stavů
- **Soubor:** `frontend-spa/src/views/RecordDetailView.vue`
- **Popis:** Stránka detailu záznamu zobrazuje zároveň stage changer (pipeline stages) i starý status progressbar (`displayedStatuses` = hardcodovaný enum new/contacted/proposal/…). Uživatel vidí obojí současně, což je matoucí.
- **Cíl:** Stage-based progressbar by měl starý status progressbar nahradit, nikoli doplnit.

### 3. RecordsView — `filterStageId` se nepromítá do URL
- **Soubor:** `frontend-spa/src/views/RecordsView.vue`
- **Popis:** `filterStageId` není ukládán do query parametrů URL (na rozdíl od `category_id` a `status`). Po refreshi nebo sdílení odkazu se stav filtru ztratí.
- **Cíl:** Synchronizovat `filterStageId` s URL query parametry stejně jako ostatní filtry.

---

## 🟠 Důležité (UX friction)

### 4. PipelineSettingsView — chybí drag-and-drop řazení stages
- **Soubor:** `frontend-spa/src/views/PipelineSettingsView.vue`
- **Popis:** Pořadí stages lze měnit pouze editací číselného pole `order`. Projekt již obsahuje závislost `VueDraggable` (používá ji `DashboardView`).
- **Cíl:** Přidat drag-and-drop handle na řádky stages pomocí existující `VueDraggable` komponenty.

### 5. RecordDetailView — Tasks endpoint ignoruje `record_id`
- **Soubor:** `frontend-spa/src/views/RecordDetailView.vue` → `loadTasks()`
- **Popis:** Funkce `loadTasks()` volá `/api/v1/crm/tasks?page_size=100` a filtruje výsledky client-side podle `task.lead_id === leadId`. U firem s mnoha úkoly se zbytečně načítá vše.
- **Cíl:** Přidat `record_id` jako query parametr do API volání, filtrovat server-side.

### 6. Kanban sloupce — chybí empty state
- **Soubor:** `frontend-spa/src/views/RecordsView.vue` (kanban view)
- **Popis:** Pokud stage nemá žádné záznamy, sloupec je prázdný bez jakéhokoli vizuálního indikátoru.
- **Cíl:** Přidat placeholder „Žádné záznamy" nebo drop-zone UI do prázdných kanban sloupců.

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

### 11. EntitySidebarActionPicker inline form — chybí validace a feedback
- **Soubor:** `frontend-spa/src/components/EntitySidebarActionPicker.vue`
- **Popis:** Inline form `addActivity()` nemá error handling ani success toast — na rozdíl od `StreamlineCreateModal`, který volá `toast.success()` / `toast.error()`. Uživatel po odeslání nevidí žádnou zpětnou vazbu.
- **Cíl:** Přidat toast notifikace (success/error) po odeslání inline formu.

---

## 🟢 Nízká priorita / polishing

### 12. RecordDetailView — chybí breadcrumb navigace
- **Soubor:** `frontend-spa/src/views/RecordDetailView.vue`
- **Popis:** Stránka detailu záznamu nemá breadcrumb zpět do `RecordsView` (ani do správné kategorie). Jediná možnost návratu je tlačítko zpět v prohlížeči.
- **Cíl:** Přidat breadcrumb lištu: Kategorie → Název záznamu.

### 13. PipelineSettingsView — `isAdminOrOwner` vždy `true`
- **Soubor:** `frontend-spa/src/views/PipelineSettingsView.vue`
- **Popis:** `isAdminOrOwner` je implementováno jako `!!firmStore.activeFirm` — vždy true, pokud je firma aktivní. Chybí skutečná role-based kontrola.
- **Cíl:** Implementovat skutečnou kontrolu role (owner/admin) pomocí `authStore` nebo `firmStore`.

### 14. Dark mode — hardcodované barvy v grafech a badges
- **Soubor:** `frontend-spa/src/views/DashboardView.vue`
- **Popis:** Chart.js i status badges používají hardcodované hex barvy (`#3b82f6`, `#22c55e` atd.), které v dark mode nevypadají dobře.
- **Cíl:** Použít CSS custom properties nebo dark mode varianty barev pro grafy a badges.

### 15. RecordsView — „Smazat filtry" neresetuje pipeline filtry
- **Soubor:** `frontend-spa/src/views/RecordsView.vue`
- **Popis:** Funkce `clearAdvancedFilters()` resetuje pokročilé filtry, ale netýká se `filterCategoryId` ani `filterStageId`.
- **Cíl:** Globální „Smazat filtry" by měl resetovat všechny aktivní filtry včetně pipeline filtrů.

---

## Legenda priorit

| Symbol | Priorita | Popis |
|--------|----------|-------|
| 🔴 | Prioritní | Chyby konzistence, zavádějící UX |
| 🟠 | Důležité | Výrazný UX friction, zbytečná práce uživatele |
| 🟡 | Střední | Zlepšení kvality UX, zpětná vazba |
| 🟢 | Nízká | Polishing, edge cases |

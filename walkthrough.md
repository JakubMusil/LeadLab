# Walkthrough — Detail views refactor + icon cleanup

## Cíl
Sjednotit detail Realizace a detail Správy s detailem Leadu. Odstranit milníky (nahradit streamline toolem). Opravit všechny ikony v šablonách – pouze @heroicons/vue/24/outline.

---

## Kroky

### Krok 1 — MilestoneTool (streamline backend + frontend)
- [x] Přidat `MilestoneTool` do `crm/streamline/tools.py`
- [x] Přidat do `BUILTIN_TOOLS`
- [x] Přidat `"milestone"` do toolbaru realizace v `crm/streamline/api.py`
- [x] Přidat `FlagIcon` mapping pro `"milestone"` do `ActivityTimeline.vue` heroIconMap

### Krok 2 — Refactor RealizationDetailView
- [x] Odstranit systém záložek (milníky, úkoly, nabídky, dokumenty)
- [x] Odstranit veškerý kód spojený s milníky (refs, funkce, computed)
- [x] Rozložení přesně jako Lead detail: 2 sloupce, vždy zobrazeno, žádné záložky
- [x] Pravý sloupec: box s detaily realizace + EntitySidebarActionPicker + nabídky + dokumenty
- [x] Opravit emoji ikony (🛠 → WrenchScrewdriverIcon, 📁 → FolderOpenIcon, 🗑 → TrashIcon)

### Krok 3 — Refactor ManagementDetailView
- [x] Odstranit systém záložek (úkoly, nabídky, dokumenty)
- [x] Rozložení přesně jako Lead detail: 2 sloupce, vždy zobrazeno, žádné záložky
- [x] Pravý sloupec: box s detaily správy + EntitySidebarActionPicker + nabídky + dokumenty
- [x] Opravit emoji ikony (📋 → ClipboardDocumentListIcon, 📁 → FolderOpenIcon, 🗑 → TrashIcon)

### Krok 4 — Oprava ikon ve všech šablonách
- [x] TaskTemplatesView.vue — 📋, 🗑
- [x] TaskDetailView.vue — 📋, 🗑, ✕ close buttons
- [x] TasksView.vue — 🗑, ✕
- [x] DocumentsView.vue — 📁, 🗑
- [x] CustomersView.vue — 🗑
- [x] LeadsView.vue — 🗑, ✕
- [x] AutomationsView.vue — 🗑, ✕
- [x] AppShell.vue — 🗑 (v mapě notifikací)
- [x] DashboardView.vue — 📋 (v mapě notifikací)
- [x] ManagementView.vue — ✕

---

## Poznámky
- Ikonset: **@heroicons/vue/24/outline** (flat, simple)
- Znaky ✓ / ✕ jako **textové checkmarky** v marketingových seznamech (MarketingView, SettingsView) NECHÁVÁME — nejde o akční ikony
- Znaky ✓ / ✕ jako **akční/UI ikony** (zavírací tlačítko, checkbox) NAHRAZUJEME heroicons
- LeadDetailView je referenční vzor pro layout

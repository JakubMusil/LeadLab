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

### Krok 4 — Oprava ikon ve VŠECH šablonách
- [x] TaskDetailView.vue — ⭐ → StarIcon, 📌 → MapPinIcon, 🗄 → ArchiveBoxIcon, ✓ → CheckIcon, ✅ → CheckCircleIcon, 🗑 → TrashIcon, ✕ → XMarkIcon, ❌ → XCircleIcon, 🔔 → BellIcon, 📋 → ClipboardDocumentListIcon, 🔗 → LinkIcon, ↗️ → ArrowTopRightOnSquareIcon, 📄 → DocumentIcon, ⏰ → ClockIcon, ⛔ → XCircleIcon
- [x] TasksView.vue — ⭐ → StarIcon, 📌 → MapPinIcon, 🗄 → ArchiveBoxIcon, 🔔 → BellIcon, ☰ → Bars3Icon, ⊞ → Squares2X2Icon, ⬛ → ViewColumnsIcon, 📊 → ChartBarIcon, 👤 → UserIcon, 📅 → CalendarDaysIcon
- [x] LeadsView.vue — ✎ → PencilSquareIcon, 🗑 → TrashIcon, ⊞ → Squares2X2Icon, ☰ → Bars3Icon
- [x] RealizationsView.vue + ManagementView.vue — ✎ → PencilSquareIcon, ✕ → XMarkIcon
- [x] CustomerDetailView.vue — ✕ → XMarkIcon, 🏢 → BuildingOfficeIcon, 👤 → UserIcon
- [x] LeadDetailView.vue — ✕ → XMarkIcon
- [x] CustomersView.vue — 🗑 → TrashIcon, 👤 → UserIcon, 🏢 → BuildingOfficeIcon
- [x] SettingsView.vue — ✓ → CheckIcon, ⭐ → StarIcon, 🗑 → TrashIcon
- [x] MarketingView.vue — ✓ → CheckIcon, ◎ → FunnelIcon, 👥 → UserGroupIcon, 📊 → ChartBarIcon
- [x] StreamlineItemList.vue — ✓ → CheckIcon, ☑️ → ClipboardDocumentCheckIcon, 📋 → ClipboardDocumentListIcon, 🗑 → TrashIcon
- [x] ToastContainer.vue — ✓ → CheckIcon, ✕ → XMarkIcon, ℹ → InformationCircleIcon
- [x] DateRangePicker.vue — ✕ → XMarkIcon
- [x] CommandPalette.vue — všechny emoji ikony → heroicon komponenty (refactor)
- [x] ContextMenu.vue — podpora Component (nejen string) jako icon
- [x] CatalogView.vue — ✕ → XMarkIcon
- [x] TeamView.vue — ✕ → XMarkIcon, 👤 → UserIcon
- [x] ProposalBuilderView.vue — ✓ → CheckIcon, 🗑 → TrashIcon
- [x] ProposalTemplatesView.vue — 📄 → DocumentIcon, ✕ → XMarkIcon
- [x] PublicTaskView.vue — ✓ → CheckIcon
- [x] TimesheetView.vue — ✕ → XMarkIcon
- [x] SuperAdminView.vue — ✓/✗ → CheckIcon/XMarkIcon
- [x] OnboardingView.vue — ✓/○ → CheckIcon/MinusCircleIcon, 🎉 → CheckCircleIcon
- [x] AcceptInviteView.vue — 🎉 → CheckCircleIcon
- [x] ReportsView.vue — 📄 → DocumentIcon
- [x] PublicProposalView.vue — 📄 → DocumentIcon, ⏰ → ClockIcon, 📋 → ClipboardDocumentListIcon, ✓/✗ → CheckIcon/XMarkIcon, 🎉/👋 → CheckCircleIcon/HandRaisedIcon
- [x] GanttView.vue — 👤 (JS string) odstraněn

---

## Poznámky
- Ikonset: **@heroicons/vue/24/outline** (flat, jednoduché)
- ContextMenu nyní podporuje `icon?: string | Component`
- CommandPalette nyní používá heroicon Component místo emoji stringů
- Build prošel bez chyb (`npx vite build`)

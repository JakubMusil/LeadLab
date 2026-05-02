# Safe Remove — Implementační plán (Soft / Shadow DELETE)

## Cíl

Každé mazání entit uživatelem musí:
1. Být potvrzeno v modálním okně (žádný `window.confirm()`).
2. Zanechat záznam v DB s příznakem smazání (`is_deleted = True`), časem (`deleted_at`) a autorem (`deleted_by`).
3. Mít plánovaný čas skutečného smazání z DB (`purge_after`).
4. Automaticky (Celery beat) provést hard-delete po uplynutí ochranné lhůty (výchozí: 30 dní).
5. Do té doby být pro uživatele neviditelný **nebo** (případ StreamlineItem) vizuálně označený jako odstraněný.

### Aktuální stav

- `Activity` — soft-delete **hotovo** (migrace 0048, API endpoint, frontend tombstone). `purge_after` doplněno migrací 0056.
- `Customer`, `Lead`, `Task`, `Realization`, `Management` — soft-delete hotovo (migrace 0055, API endpointy, frontend ConfirmDeleteModal).
- Ostatní entity — stále hard-delete; budou řešeny v dalších sezeních.

---

## Fáze 1 — Backend: Infrastruktura (`SoftDeleteMixin`)

**Cíl:** Centralizovat soft-delete logiku do jednoho místa, aby každý model stačil zdědit mixin.

### Úkoly

- [x] **1.1** Vytvořit `crm/soft_delete.py`:
  - `SoftDeleteMixin` — abstraktní mixin přidávající pole `is_deleted`, `deleted_at`, `deleted_by`, `purge_after` (DateTimeField, null/blank).
  - `SoftDeleteManager` — výchozí manager vracející pouze `is_deleted=False`; alternativní `all_objects` manager bez filtru.
  - Metodu `soft_delete(user)` na modelu: nastaví pole, uloží `update_fields`.
- [x] **1.2** `SoftDeleteMixin` jako samostatný mixin; do modelů se přidává vedle `TenantModel`.
- [x] **1.3** Přidat pomocnou funkci `perform_soft_delete(instance, user, purge_days=30)` do `crm/soft_delete.py`.

---

## Fáze 2 — Backend: Migrace

**Cíl:** Přidat soft-delete pole ke všem cílovým modelům jednou migrací na entitu (nebo hromadnou migrací).

### Priority A — hlavní business entity

- [x] **2.1** `Customer` — přidat `is_deleted`, `deleted_at`, `deleted_by`, `purge_after` (migrace 0055)
- [x] **2.2** `Lead` — přidat `is_deleted`, `deleted_at`, `deleted_by`, `purge_after` (migrace 0055)
- [x] **2.3** `Task` — přidat `is_deleted`, `deleted_at`, `deleted_by`, `purge_after` (migrace 0055)
- [x] **2.4** `Realization` — přidat `is_deleted`, `deleted_at`, `deleted_by`, `purge_after` (migrace 0055)
- [x] **2.5** `Management` — přidat `is_deleted`, `deleted_at`, `deleted_by`, `purge_after` (migrace 0055)

### Priority B — finanční / ERP entity

- [ ] **2.6** `Proposal` — přidat soft-delete pole
- [ ] **2.7** `TimeEntry` — přidat soft-delete pole
- [ ] **2.8** `ExpenseItem` — přidat soft-delete pole
- [ ] **2.9** `RevenueItem` — přidat soft-delete pole
- [ ] **2.10** `Milestone` — přidat soft-delete pole

### Priority C — podpůrné entity

- [ ] **2.11** `Document` — přidat soft-delete pole (smazání fyzického souboru odložit na purge krok)
- [ ] **2.12** `StreamlineItem` — přidat `is_deleted`, `deleted_at`, `deleted_by` (bez `purge_after`)
- [ ] **2.13** `AutomationRule` — přidat soft-delete pole
- [ ] **2.14** `ProposalTemplate` — přidat soft-delete pole
- [ ] **2.15** `FirmProposalItem` (katalog) — přidat soft-delete pole
- [ ] **2.16** `TaskTemplate` — přidat soft-delete pole
- [ ] **2.17** `TaskCustomField` — přidat soft-delete pole
- [x] **2.18** `Activity` — přidat `purge_after` pole (migrace 0056)

> Poznámka: `TaskDependency`, `ProposalItem`, `ProposalTemplateItem`, `SavedView`, `TaskTimeLog` — tyto relační/config záznamy mohou zůstat s hard-delete (nízké riziko ztráty dat). Posouzení na reviewu.

---

## Fáze 3 — Backend: Aktualizace API endpointů (Priority A)

**Cíl:** Změnit DELETE endpointy tak, aby prováděly soft-delete místo hard-delete.

- [x] **3.1** `DELETE /api/v1/crm/directory/{customer_id}` (`delete_customer` v `api.py`)
- [x] **3.2** `DELETE /api/v1/crm/opportunities/{lead_id}` (`delete_lead`)
- [x] **3.3** `DELETE /api/v1/crm/tasks/{task_id}` (`delete_task`)
- [x] **3.4** `DELETE /api/v1/crm/realizations/{realization_id}` (`delete_realization` v `realization_api.py`)
- [x] **3.5** `DELETE /api/v1/crm/management/{management_id}` (`delete_management` v `management_api.py`)

---

## Fáze 4 — Backend: Aktualizace API endpointů (Priority B + C)

- [ ] **4.1** `DELETE /api/v1/crm/proposals/{proposal_id}` (`delete_proposal` v `proposals_api.py`)
- [ ] **4.2** `DELETE /api/v1/erp/time-entries/{entry_id}` (`delete_time_entry` v `erp_api.py`)
- [ ] **4.3** `DELETE /api/v1/erp/expenses/{item_id}` (`delete_expense`)
- [ ] **4.4** `DELETE /api/v1/erp/revenues/{item_id}` (`delete_revenue`)
- [ ] **4.5** `DELETE /api/v1/erp/documents/{document_id}` (`delete_document` v `documents_api.py`) — fyzický soubor smazat až v purge tasku
- [ ] **4.6** `DELETE /api/v1/crm/items/{item_id}` (`delete_streamline_item`) — soft-delete, vrátit tombstone (speciální chování viz Fáze 9)
- [ ] **4.7** `DELETE /api/v1/crm/realizations/{realization_id}/milestones/{milestone_id}` (`delete_milestone`)
- [ ] **4.8** `DELETE /api/v1/crm/automations/{rule_id}` (`delete_automation_rule`)
- [ ] **4.9** `DELETE /api/v1/crm/task-templates/{template_id}` (`delete_task_template`)
- [ ] **4.10** `DELETE /api/v1/crm/firm-proposal-items/{item_id}` (`delete_firm_proposal_item`)
- [ ] **4.11** `DELETE /api/v1/crm/custom-fields/{field_id}` (`delete_custom_field`)
- [ ] **4.12** `DELETE /api/v1/crm/opportunities/{lead_id}/attachments/{attachment_id}` — fyzický soubor odložit na purge
- [ ] **4.13** `DELETE /api/v1/crm/tasks/{task_id}/documents/{document_id}` — fyzický soubor odložit na purge
- [ ] **4.14** Aktualizovat querysets / filtry ve všech GET listech, aby vylučovaly `is_deleted=True` záznamy (tam kde to ještě není).

---

## Fáze 5 — Backend: Celery purge task

**Cíl:** Automaticky provést hard-delete entit, jejichž `purge_after` uplynulo.

- [x] **5.1** Přidat do `crm/tasks.py` funkci `purge_soft_deleted_records()`.
- [x] **5.2** Zaregistrovat task v `CELERY_BEAT_SCHEDULE` (každou noc ve 03:00 UTC). Přidán `SOFT_DELETE_PURGE_DAYS` do settings.
- [x] **5.3** `Activity.purge_after` — migrace 0056. Endpoint `delete_activity` nyní také nastavuje `purge_after`.

---

## Fáze 6 — Frontend: Komponenta `ConfirmDeleteModal`

**Cíl:** Nahradit všechny nekonzistentní způsoby potvrzení smazání jednou reusable komponentou.

- [x] **6.1** Vytvořit `frontend-spa/src/components/ui/ConfirmDeleteModal.vue`.
- [x] **6.2** Exportovat komponentu z `frontend-spa/src/components/ui/index.ts`.
- [x] **6.3** Přidat i18n klíče (`deleteModal.*`) do lokalizačních souborů cs, en, de, pl.

---

## Fáze 7 — Frontend: Hlavní entity

**Cíl:** Nahradit stávající mazání u hlavních entit novým soft-delete flow s `ConfirmDeleteModal`.

- [x] **7.1** `LeadsView.vue` — nahrazen inline modal → `ConfirmDeleteModal`.
- [x] **7.2** `CustomerDetailView.vue` — nahrazen `window.confirm()` → `ConfirmDeleteModal`.
- [x] **7.3** `TaskDetailView.vue` — nahrazen inline potvrzovací sekce → `ConfirmDeleteModal`.
- [x] **7.4** `RealizationsView.vue` — nahrazen inline modal → `ConfirmDeleteModal`.
- [x] **7.5** `ManagementView.vue` — nahrazen inline modal → `ConfirmDeleteModal`.

---

## Fáze 8 — Frontend: Sekundární entity

- [ ] **8.1** `ProposalBuilderView.vue` — nahradit `window.confirm()` → `ConfirmDeleteModal` pro mazání návrhů.
- [ ] **8.2** `TimesheetView.vue` — přidat `ConfirmDeleteModal` před smazáním TimeEntry.
- [ ] **8.3** `AutomationsView.vue` — přidat `ConfirmDeleteModal` před smazáním pravidla.
- [ ] **8.4** `CatalogView.vue` — přidat `ConfirmDeleteModal` před smazáním položky katalogu.
- [ ] **8.5** `SettingsView.vue` — nahradit `window.confirm()` pro mazání custom fields → `ConfirmDeleteModal` (mazání workspace ponechat jako doposud — má vlastní speciální UX).
- [ ] **8.6** `RealizationDetailView.vue` / `ManagementDetailView.vue` — přidat `ConfirmDeleteModal` pro mazání dokumentů, milníků a ERP položek.
- [ ] **8.7** `TaskTemplatesView.vue` — přidat `ConfirmDeleteModal` pro mazání šablon.
- [ ] **8.8** `LeadDetailView.vue` — přidat `ConfirmDeleteModal` pro mazání příloh.
- [ ] **8.9** Stores (`stores/tasks.ts`, `stores/leads.ts`, `stores/customers.ts`, …) — v žádném store není třeba přidávat confirm; store jen provede API call; UX confirm je vždy na úrovni view/komponenty.

---

## Fáze 9 — StreamlineItem: Speciální chování „označeno jako odstraněné"

**Cíl:** StreamlineItem (TODO/subtask) se po smazání nemá skrýt, ale zobrazit jako přeškrtnutý/odstraněný s metadaty.

- [ ] **9.1** Backend — `delete_streamline_item` endpoint vrátí 200 + `StreamlineItemOut` s tombstone daty (`is_deleted`, `deleted_at`, `deleted_by_name`) místo 204.
- [ ] **9.2** `StreamlineItemList.vue` — tombstone položky zobrazit přeškrtnuté s textem „Odstraněno uživatelem X dne Y". Povolené akce: žádné (jen pro informaci).
- [ ] **9.3** Přidat možnost „skrýt odstraněné" přepínač v `StreamlineItemList.vue` (opt-in).

---

## Fáze 10 — Audit viditelnost v UI

**Cíl:** Uživatel by měl vidět, kdo a kdy entitu smazal — zejména u Activity tombstone (již existuje) a u StreamlineItem.

- [ ] **10.1** `ActivityTimeline.vue` — zkontrolovat, že tombstone zobrazuje `deleted_by_name` a `deleted_at` (existující implementace prověřit).
- [ ] **10.2** `StreamlineItemList.vue` — tombstone zobrazit s `deleted_by_name` + `deleted_at` (navazuje na Fázi 9).
- [ ] **10.3** Pro ostatní entity (Customer, Lead, Task, …) — po soft-delete jsou z UI skryty; audit informace jsou dostupné pouze přes admin (Django admin nebo budoucí audit log). Toto je akceptovatelné chování v aktuální fázi.

---

## Technické poznámky

### Ochranná lhůta
Výchozí hodnota `purge_days = 30` dní. Konfigurovatelná přes `settings.SOFT_DELETE_PURGE_DAYS` (env: `SOFT_DELETE_PURGE_DAYS`).

### Zpětná kompatibilita API
Stávající klienti volající DELETE endpointy dostávají 204 (zachováno). Frontend skrývá entity z listingu (SoftDeleteManager automaticky filtruje `is_deleted=False`).

### Manager a existující dotazy
Po přidání `SoftDeleteMixin` filtruje výchozí manager automaticky `is_deleted=False`. Pro admin/audit použít `Model.all_objects.all()`.

### Pořadí implementace
Doporučené pořadí: Fáze 1 → 2 (postupně per entity) → 3 → 5 → 6 → 7 → 4 → 8 → 9 → 10.
Fáze 1, 5, 6 jsou blokující pro ostatní. Fáze 2–4 a 7–8 lze paralelizovat po entitách.

### Co bylo hotovo v session 1 (2026-05-02)
- Fáze 1 kompletní: `crm/soft_delete.py`.
- Fáze 2A kompletní: migrace 0055 + migrace 0056.
- Fáze 3 kompletní: 5 Priority A DELETE endpointů přepsáno na soft-delete.
- Fáze 5 kompletní: purge task + beat schedule + SOFT_DELETE_PURGE_DAYS setting.
- Fáze 6 kompletní: ConfirmDeleteModal.vue + export + i18n.
- Fáze 7 kompletní: 5 hlavních views přepsáno.

### Co zbývá pro příští session
- Fáze 2B + 2C: migrace pro Proposal, TimeEntry, ExpenseItem, RevenueItem, Milestone, Document, StreamlineItem, AutomationRule, ProposalTemplate, FirmProposalItem, TaskTemplate, TaskCustomField.
- Fáze 4: DELETE endpointy pro Priority B + C entity.
- Fáze 8: Frontend pro sekundární entity (ProposalBuilderView, TimesheetView, AutomationsView, CatalogView, SettingsView, RealizationDetailView, ManagementDetailView, TaskTemplatesView, LeadDetailView).
- Fáze 9: StreamlineItem tombstone chování.
- Fáze 10: Audit viditelnost (zkontrolovat ActivityTimeline tombstone).

# Safe Remove — Implementační plán (Soft / Shadow DELETE)

## Cíl

Každé mazání entit uživatelem musí:
1. Být potvrzeno v modálním okně (žádný `window.confirm()`).
2. Zanechat záznam v DB s příznakem smazání (`is_deleted = True`), časem (`deleted_at`) a autorem (`deleted_by`).
3. Mít plánovaný čas skutečného smazání z DB (`purge_after`).
4. Automaticky (Celery beat) provést hard-delete po uplynutí ochranné lhůty (výchozí: 30 dní).
5. Do té doby být pro uživatele neviditelný **nebo** (případ StreamlineItem) vizuálně označený jako odstraněný.

### Aktuální stav

- `Activity` — soft-delete **hotovo** (migrace 0048, API endpoint, frontend tombstone). Chybí pouze plánované smazání.
- Všechny ostatní entity — hard-delete (`.delete()`), různorodý frontend (native `confirm()`, inline modaly, přímé volání).

---

## Fáze 1 — Backend: Infrastruktura (`SoftDeleteMixin`)

**Cíl:** Centralizovat soft-delete logiku do jednoho místa, aby každý model stačil zdědit mixin.

### Úkoly

- [ ] **1.1** Vytvořit `crm/soft_delete.py`:
  - `SoftDeleteMixin` — abstraktní mixin přidávající pole `is_deleted`, `deleted_at`, `deleted_by`, `purge_after` (DateTimeField, null/blank).
  - `SoftDeleteManager` — výchozí manager vracející pouze `is_deleted=False`; alternativní `all_objects` manager bez filtru.
  - Metodu `soft_delete(user)` na modelu: nastaví pole, uloží `update_fields`.
- [ ] **1.2** Upravit `TenantModel` (nebo nechat jako samostatný mixin — dle rozhodnutí) tak, aby bylo snadné přidat mixin do libovolného modelu.
- [ ] **1.3** Přidat pomocnou funkci `perform_soft_delete(instance, user, purge_days=30)` do `crm/soft_delete.py` pro použití v API endpointech (nastaví `purge_after = now + purge_days`).

---

## Fáze 2 — Backend: Migrace

**Cíl:** Přidat soft-delete pole ke všem cílovým modelům jednou migrací na entitu (nebo hromadnou migrací).

### Priority A — hlavní business entity

- [ ] **2.1** `Customer` — přidat `is_deleted`, `deleted_at`, `deleted_by`, `purge_after`
- [ ] **2.2** `Lead` — přidat `is_deleted`, `deleted_at`, `deleted_by`, `purge_after`
- [ ] **2.3** `Task` — přidat `is_deleted`, `deleted_at`, `deleted_by`, `purge_after`
- [ ] **2.4** `Realization` — přidat `is_deleted`, `deleted_at`, `deleted_by`, `purge_after`
- [ ] **2.5** `Management` — přidat `is_deleted`, `deleted_at`, `deleted_by`, `purge_after`

### Priority B — finanční / ERP entity

- [ ] **2.6** `Proposal` — přidat soft-delete pole
- [ ] **2.7** `TimeEntry` — přidat soft-delete pole
- [ ] **2.8** `ExpenseItem` — přidat soft-delete pole
- [ ] **2.9** `RevenueItem` — přidat soft-delete pole
- [ ] **2.10** `Milestone` — přidat soft-delete pole

### Priority C — podpůrné entity

- [ ] **2.11** `Document` — přidat soft-delete pole (smazání fyzického souboru odložit na purge krok)
- [ ] **2.12** `StreamlineItem` — přidat `is_deleted`, `deleted_at`, `deleted_by` (bez `purge_after` — StreamlineItem se pouze označuje, nemaže)
- [ ] **2.13** `AutomationRule` — přidat soft-delete pole
- [ ] **2.14** `ProposalTemplate` — přidat soft-delete pole
- [ ] **2.15** `FirmProposalItem` (katalog) — přidat soft-delete pole
- [ ] **2.16** `TaskTemplate` — přidat soft-delete pole
- [ ] **2.17** `TaskCustomField` — přidat soft-delete pole
- [ ] **2.18** `Activity` — přidat `purge_after` pole (chybí; `is_deleted` a spol. jsou již hotové)

> Poznámka: `TaskDependency`, `ProposalItem`, `ProposalTemplateItem`, `SavedView`, `TaskTimeLog` — tyto relační/config záznamy mohou zůstat s hard-delete (nízké riziko ztráty dat). Posouzení na reviewu.

---

## Fáze 3 — Backend: Aktualizace API endpointů (Priority A)

**Cíl:** Změnit DELETE endpointy tak, aby prováděly soft-delete místo hard-delete. Schémata odpovědí doplnit o soft-delete pole.

- [ ] **3.1** `DELETE /api/v1/crm/directory/{customer_id}` (`delete_customer` v `api.py`)
  - Volat `perform_soft_delete(customer, request.user)` místo `.delete()`.
  - Vrátit 200 + `CustomerOut` s tombstone daty (nebo ponechat 204 a jen skrýt z listingu).
  - `CustomerOut` schema doplnit o `is_deleted`, `deleted_at`, `deleted_by_name`.
- [ ] **3.2** `DELETE /api/v1/crm/opportunities/{lead_id}` (`delete_lead`)
  - Stejný vzor jako 3.1. `LeadOut` schema doplnit.
- [ ] **3.3** `DELETE /api/v1/crm/tasks/{task_id}` (`delete_task`)
  - Stejný vzor. `TaskOut` schema doplnit.
- [ ] **3.4** `DELETE /api/v1/crm/realizations/{realization_id}` (`delete_realization` v `realization_api.py`)
- [ ] **3.5** `DELETE /api/v1/crm/management/{management_id}` (`delete_management` v `management_api.py`)

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

- [ ] **5.1** Přidat do `crm/tasks.py` funkci `purge_soft_deleted_records()`:
  - Projde všechny modely se soft-delete a smaže záznamy kde `is_deleted=True AND purge_after <= now()`.
  - Pro `Document` s fyzickým souborem zavolat `doc.file.delete(save=False)` před `doc.delete()`.
  - Logovat počty smazaných záznamů (`logger.info`).
- [ ] **5.2** Zaregistrovat task v `CELERY_BEAT_SCHEDULE` (`leadlab/settings.py`):
  ```python
  'purge-soft-deleted-records': {
      'task': 'crm.tasks.purge_soft_deleted_records',
      'schedule': crontab(hour=3, minute=0),  # každou noc ve 03:00 UTC
  },
  ```
- [ ] **5.3** Přidat `purge_after` ke stávajícímu `Activity` modelu (migrace) a zahrnout ho do purge tasku.

---

## Fáze 6 — Frontend: Komponenta `ConfirmDeleteModal`

**Cíl:** Nahradit všechny nekonzistentní způsoby potvrzení smazání jednou reusable komponentou.

- [ ] **6.1** Vytvořit `frontend-spa/src/components/ui/ConfirmDeleteModal.vue`:
  - Props: `open: boolean`, `title?: string`, `message?: string`, `loading?: boolean`.
  - Emits: `confirm`, `cancel`.
  - Postavit na existujícím `Modal.vue`.
  - Tlačítko "Smazat" červené (destructive), tlačítko "Zrušit" neutrální.
  - Klávesa `Escape` zavře modal.
- [ ] **6.2** Exportovat komponentu z `frontend-spa/src/components/ui/index.ts`.
- [ ] **6.3** Přidat i18n klíče pro výchozí texty (`deleteModal.title`, `deleteModal.message`, `deleteModal.confirm`, `deleteModal.cancel`) do lokalizačních souborů.

---

## Fáze 7 — Frontend: Hlavní entity

**Cíl:** Nahradit stávající mazání u hlavních entit novým soft-delete flow s `ConfirmDeleteModal`.

- [ ] **7.1** `LeadsView.vue` — nahradit inline modal `ConfirmDeleteModal`; po smazání entitu skrýt z listu (nebo zobrazit tombstone dle návrhu).
- [ ] **7.2** `CustomerDetailView.vue` — nahradit `window.confirm()` → `ConfirmDeleteModal`; přesměrovat na `/customers` po potvrzení.
- [ ] **7.3** `TaskDetailView.vue` — nahradit inline potvrzovací sekci → `ConfirmDeleteModal`; po smazání přesměrovat na `/tasks`.
- [ ] **7.4** `RealizationsView.vue` — nahradit inline modal → `ConfirmDeleteModal`.
- [ ] **7.5** `ManagementView.vue` — nahradit inline modal → `ConfirmDeleteModal`.

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
Výchozí hodnota `purge_days = 30` dní. Může být konfigurovatelná přes `settings.SOFT_DELETE_PURGE_DAYS`.

### Zpětná kompatibilita API
Stávající klienti volající DELETE endpointy mohou dostávat 200 + tělo místo 204. Je třeba ověřit, zda to nenarušuje stávající frontend (všechny volání kontrolují `res.ok`, ne status kód). Alternativně: zachovat 204 a skrýt entitu z listingu bez tombstone — pro entity jiné než Activity a StreamlineItem je to preferované chování.

### Manager a existující dotazy
Po přidání `SoftDeleteMixin` bude výchozí manager filtrovat `is_deleted=False`. Je nutné projít existující dotazy a tam kde je potřeba vidět smazané záznamy (např. admin, audit), použít `Model.all_objects.all()`.

### Pořadí implementace
Doporučené pořadí: Fáze 1 → 2 (postupně per entity) → 3 → 5 → 6 → 7 → 4 → 8 → 9 → 10.
Fáze 1, 5, 6 jsou blokující pro ostatní. Fáze 2–4 a 7–8 lze paralelizovat po entitách.

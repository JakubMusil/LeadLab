# Pipeline Record Architecture

Cílem je nahradit hardcodované entity **Lead**, **Realization** a **Management**
jedním obecným modelem **PipelineRecord** řízeným dynamicky konfigurovatelnými
**kategoriemi** a **stages**.  
Projekt je ve fázi vývoje — migrace se nepřenáší, databáze se vždy vytvoří znova.

---

## Přehled fází

| # | Název | Stav |
|---|-------|------|
| 1 | Smazat Realization + Management | ✅ |
| 2 | Přejmenovat Lead → PipelineRecord + nové modely | ✅ |
| 3 | API – Category/Stage konfigurace + Records CRUD | ✅ |
| 4 | Seed command + onboarding hook | ✅ |
| 5 | Frontend stores + API klient | ✅ |
| 6 | Settings UI pro správu kategorií a stages | ✅ |
| 7 | RecordsView + RecordDetailView (vzor: LeadsView) | ✅ |
| 8 | AppShell navigace + Router update | ✅ |

---

## Odškrtávací checklist

### Fáze 1 — Smazat Realization + Management ✅

#### Backend
- [x] `crm/models.py` — smazat třídy `RealizationStatus`, `Realization`, `Milestone`, `ManagementType`, `ManagementStatus`, `Management`
- [x] `crm/models.py` → `Activity` — smazat FK pole `realization` a `management` + indexy
- [x] `crm/models.py` → `Task` — smazat FK pole `realization` a `management`
- [x] `crm/models.py` → `Document` — smazat FK pole `realization` a `management` + indexy
- [x] Smazat `crm/realization_api.py`
- [x] Smazat `crm/management_api.py`
- [x] `leadlab/api.py` — odstranit importy a `add_router` pro `realization_router` a `management_router`
- [x] `crm/api.py` — smazat importy `Management`, `Realization`; smazat endpointy `realization_metrics`, `sla_compliance`; smazat realization/management větve v action hubu; vyčistit `_task_out` od realization/management polí; vyčistit voice memo endpoint; vyčistit profitability endpoint
- [x] `crm/tasks.py` — smazat `_action_create_realization`, `_action_create_management` a jejich volání; vyčistit weekly digest od realization/SLA stats
- [x] `crm/automations_api.py` — smazat šablony odkazující na realization/management
- [x] `crm/streamline/tools.py` — smazat `realization`/`management` parametry v tool schématech (řádky 1347-1348, 2071-2092)
- [x] `crm/documents_api.py` — smazat `realization_id`/`management_id` parametry a větve; vyčistit importy a `DocumentOut` schéma
- [x] Smazat všechny migrace v `crm/migrations/` (kromě `__init__.py`), spustit `makemigrations`

#### Frontend
- [x] Smazat `frontend-spa/src/views/RealizationsView.vue`
- [x] Smazat `frontend-spa/src/views/RealizationDetailView.vue`
- [x] Smazat `frontend-spa/src/views/ManagementView.vue`
- [x] Smazat `frontend-spa/src/views/ManagementDetailView.vue`
- [x] Smazat `frontend-spa/src/stores/realizations.ts`
- [x] Smazat `frontend-spa/src/stores/management.ts`
- [x] `router/index.ts` — smazat routes `/realizations`, `/realizations/:id`, `/management`, `/management/:id`
- [x] `AppShell.vue` — smazat WS handlery `realization.*` a `management.*`; smazat nav položky Realizace + Správa; smazat `WrenchScrewdriverIcon` a `ShieldExclamationIcon` imports (pokud jsou jen pro tyto nav položky)

---

### Fáze 2 — Přejmenovat Lead → PipelineRecord + nové modely ✅

#### Přejmenování Lead → PipelineRecord (backend)
- [x] `crm/models.py` — přejmenovat třídu `Lead` → `PipelineRecord`; přejmenovat `LeadStatus` → `RecordStatus`, `LeadSource` → `RecordSource`
- [x] `crm/models.py` → `Activity.lead` FK → přejmenovat na `record`, `related_name='activities'`
- [x] `crm/models.py` → `Task.lead` FK → přejmenovat na `record`
- [x] `crm/models.py` → `Document.lead` FK → přejmenovat na `record`
- [x] `crm/api.py` — přejmenovat `Lead*` schémata → `Record*`; endpoint `/leads` → `/records`; importy; WS event klíče `lead.*` → `record.*`
- [x] `crm/tasks.py` — přejmenovat kontextové proměnné a importy Lead→PipelineRecord
- [x] `crm/streamline/tools.py` — přejmenovat `lead_id` → `record_id` v parametrech
- [x] `crm/documents_api.py` — přejmenovat `lead_id` → `record_id`
- [x] `crm/admin.py` — přejmenovat `LeadAdmin` → `PipelineRecordAdmin`
- [x] `crm/events.py` — přejmenovat event strings `lead.*` → `record.*`

#### Přejmenování Lead → PipelineRecord (frontend)
- [x] Přejmenovat `stores/leads.ts` → `stores/records.ts`; `useLeadsStore` → `useRecordsStore`; `LeadOut`→`RecordOut`; API endpoint `/leads` → `/records`
- [x] Přejmenovat `LeadsView.vue` → `RecordsView.vue` (zatím jen rename, adaptace v Fázi 7)
- [x] Přejmenovat `LeadDetailView.vue` → `RecordDetailView.vue` (zatím jen rename, adaptace v Fázi 7)
- [x] `router/index.ts` — paths `/opportunities` → `/records`, `/opportunities/:id` → `/records/:id`
- [x] `AppShell.vue` — WS handlery `lead.*` → `record.*`; nav položka Příležitosti → Records; store reference
- [x] `composables/useI18n.ts` — přejmenovat i18n klíče `leads.*` → `records.*`

#### Nové modely v `crm/models.py`
- [x] **`Category`** — `id` UUID PK, `firm` FK (TenantModel), `name`, `slug` (auto), `icon`, `color`, `order`, `is_active`, `created_at`; `Meta: unique_together(firm, slug)`
- [x] **`Stage`** — `id` UUID PK, `category` FK→Category CASCADE, `name`, `label`, `color`, `order`, `is_terminal`, `is_won`, `created_at`; `Meta: unique_together(category, order)`
- [x] **`CategoryField`** — `id` UUID PK, `category` FK→Category CASCADE, `field_key` (choices), `is_visible`, `is_required`, `order`; `Meta: unique_together(category, field_key)`
- [x] **`Checkpoint`** — `id` UUID PK, `record` FK→PipelineRecord CASCADE, `name`, `date`, `is_completed`, `description`, `created_at`; `SoftDeleteMixin`
- [x] `PipelineRecord` — přidat pole `category` FK→Category nullable, `current_stage` FK→Stage nullable, `parent` FK→self nullable, `start_date`, `end_date`, `expires_at`, `notes`, `extra_data` JSONField

#### Migrace
- [x] Smazat celý obsah `crm/migrations/` kromě `__init__.py`
- [x] `./manage.py makemigrations crm`
- [x] `./manage.py migrate`

---

### Fáze 3 — API ✅

#### `crm/pipeline_config_api.py` (nový soubor)
- [x] `GET /categories` — list per firm
- [x] `POST /categories` — vyžaduje role owner/admin
- [x] `PATCH /categories/{id}` — rename, color, icon, order, is_active
- [x] `DELETE /categories/{id}` — 409 pokud existují records
- [x] `GET /categories/{id}/stages`
- [x] `POST /categories/{id}/stages`
- [x] `PATCH /categories/{id}/stages/{stage_id}`
- [x] `DELETE /categories/{id}/stages/{stage_id}` — 409 pokud jsou records s touto stage
- [x] `GET /categories/{id}/fields`
- [x] `POST/PATCH/DELETE /categories/{id}/fields/{field_key}`

#### `crm/records_api.py` (nový soubor — přejmenovaný a rozšířený lead sekce)
- [x] `RecordOut` schéma s `stage_progress`, `sla_color`, `checkpoints` → rozšířen o `category_id`, `current_stage_id`, `current_stage_name`, `parent_id`, `start_date`, `end_date`, `expires_at`, `notes`, `extra_data`
- [x] `GET /records` — filtry: category_id, stage_id, assigned_to_id, customer_id, parent_id, sort, pagination
- [x] `POST /records`
- [x] `GET /records/{id}`
- [x] `PATCH /records/{id}`
- [x] `DELETE /records/{id}` → soft delete
- [x] `GET /records/{id}/checkpoints`
- [x] `POST /records/{id}/checkpoints`
- [x] `PATCH /records/{id}/checkpoints/{checkpoint_id}`
- [x] `DELETE /records/{id}/checkpoints/{checkpoint_id}`

#### `leadlab/api.py`
- [x] Registrovat `pipeline_config_router`

#### WebSocket events (`crm/events.py`)
- [x] `category.updated` — broadcastován při každé změně kategorie/stage/field
- [x] `record.created`, `record.updated`, `record.deleted` — již existovaly

---

### Fáze 4 — Seed command + onboarding hook ✅

- [x] `crm/management/commands/seed_pipeline_categories.py` — vytvoří 3 výchozí kategorie (Příležitosti, Realizace, Správa) s odpovídajícími stages pro danou firmu
- [x] `firms/api.py` `create_firm` — zavolat `seed_for_firm()` při vytvoření nové firmy

---

### Fáze 5 — Frontend stores + API klient ✅

- [x] `frontend-spa/src/stores/pipeline.ts` — Pinia store: `categories`, `stages`, `records`, `currentRecord`; helpers `getStageProgress()`, `getSlaColor()`; CRUD pro Category a Stage
- [x] `frontend-spa/src/stores/records.ts` — rozšířen `RecordOut` a `RecordIn` o pipeline pole (category_id, current_stage_id, parent_id, start_date, end_date, expires_at, notes, extra_data); `RecordFilters` doplněn o category_id, stage_id, parent_id

---

### Fáze 6 — Settings UI pro správu kategorií a stages ✅

- [x] `frontend-spa/src/views/PipelineSettingsView.vue` — dvoupanelové rozložení: vlevo seznam kategorií, vpravo editace stages a polí
- [x] Route `/app/settings/pipeline` přidána do `router/index.ts`
- [x] Tlačítko "Pipeline" v SettingsView naviguje na `/app/settings/pipeline`

---

### Fáze 7 — RecordsView + RecordDetailView ✅

- [x] `RecordsView.vue` — import `usePipelineStore`; category selector v hlavičce; `filterCategoryId`/`filterStageId` filtry; `leadsByStage` computed; stage-based kanban sloupce; watch `category_id` query param
- [x] `RecordDetailView.vue` — opraveno `store.currentLead` → `store.currentRecord`; import `usePipelineStore`; Checkpoints panel (load/add/toggle/delete); Stage changer (klikatelné stage buttony); Stage progressbar (stage-based nebo status-based)

---

### Fáze 8 — AppShell + Router ✅

- [x] `router/index.ts` — `/app/records`, `/app/records/:id` routes (již byly z Fáze 2); přidána `/app/settings/pipeline`
- [x] `AppShell.vue` — import `usePipelineStore`; `fetchCategories()` v `onMounted`; dynamická navigace kategorií pod "Records" (barevné puntíky); WS handlery přejmenovat `lead.*` → `record.*`; `category.updated` WS handler → `pipelineStore.handleCategoryUpdated()`

---

## Technické poznámky

### Přejmenování Lead → PipelineRecord
Protože jde o dev prostředí bez produkčních dat, je přejmenování čisté:
- Django model `Lead` → `PipelineRecord` (DB tabulka: `crm_pipelinerecord`)
- `LeadStatus` → `RecordStatus`, `LeadSource` → `RecordSource`
- FK pole `lead` v Activity, Task, Document → `record`
- API endpoint `/api/v1/crm/leads` → `/api/v1/crm/records`
- WS events `lead.created` → `record.created` atd.
- Frontend store `useLeadsStore` → `useRecordsStore`

### Architektura Category/Stage
- **Category** = typ pipeline (Příležitosti, Realizace, Správa, …) — per-firm, konfigurovatelný
- **Stage** = krok v pipeline dané kategorie (Nový, Osloven, …) — per-category, ordered
- **PipelineRecord** má FK na Category + current_stage; pole `parent` umožňuje řetězení (Příležitost → Realizace → Správa)
- **CategoryField** = opt-in pole per Category (value_currency, date_range, expires_at, notes, source, origin_record)

### Zachované komponenty beze změny
- `ActivityTimeline.vue` — pracuje s activities, nezávisí na entitě
- `EntitySidebarActionPicker.vue` — obecná sidebar komponenta
- `useListView` composable — přebírá nový `storageKeyPrefix`
- `useMoney` composable — beze změny
- `RichTextEditor.vue` — beze změny

---

## Záznam průběhu

### 2026-05-03 — Fáze 1 + Fáze 2 dokončeny

**Fáze 1** (PR #153, branch copilot/analyze-lead-realizace-sprava):
- Smazány všechny třídy Realization, Milestone, Management z crm/models.py
- Smazány crm/realization_api.py a crm/management_api.py
- Odstraněny importy a routery z leadlab/api.py
- Vyčištěno crm/api.py, crm/tasks.py, crm/automations_api.py, crm/streamline/tools.py, crm/documents_api.py
- Frontend: smazány RealizationsView, RealizationDetailView, ManagementView, ManagementDetailView, stores/realizations.ts, stores/management.ts
- Router a AppShell.vue aktualizovány

**Fáze 2** (branch copilot/pipeline-record-architecture-progress):
- `Lead` → `PipelineRecord`, `LeadStatus` → `RecordStatus`, `LeadSource` → `RecordSource`
- Nové modely: `Category`, `Stage`, `CategoryField`, `Checkpoint`
- PipelineRecord rozšířen o pole: category, current_stage, parent, start_date, end_date, expires_at, notes, extra_data
- FK přejmenována: Activity.lead→.record, Task.lead→.record, Document.lead→.record
- crm/api.py: schémata Lead*→Record*, endpoint /leads→/records, WS eventy lead.*→record.*
- crm/tasks.py, crm/events.py, crm/admin.py, crm/documents_api.py, crm/streamline/tools.py aktualizovány
- Migrace resetovány a znovu vygenerovány (2 soubory: 0001_initial, 0002_category_etc)
- Frontend: stores/records.ts (useRecordsStore), RecordsView.vue, RecordDetailView.vue, router /records, AppShell.vue, useI18n.ts aktualizovány
- `python manage.py check` → 0 issues

### 2026-05-03 — Fáze 3 dokončena

**Fáze 3** (branch copilot/update-pipeline-record-architecture):
- Nový soubor `crm/pipeline_config_api.py`: plný CRUD pro Category, Stage, CategoryField
  - GET/POST/PATCH/DELETE /categories
  - GET/POST/PATCH/DELETE /categories/{id}/stages
  - GET/POST/PATCH/DELETE /categories/{id}/fields/{field_key}
  - DELETE vrací 409 pokud existují records/stages využívající danou entitu
  - `category.updated` WS event broadcastován při každé změně
- `crm/api.py` — rozšířen:
  - `RecordOut` doplněn o pole: category_id, current_stage_id, current_stage_name, parent_id, start_date, end_date, expires_at, notes, extra_data
  - `RecordIn` / `RecordUpdateIn` doplněny o stejná pole
  - `GET /records` doplněn o filtry: category_id, stage_id, customer_id, parent_id
  - `POST /records` a `PATCH /records/{id}` validují category/stage/parent FK
  - Přidány Checkpoint endpointy: GET/POST /records/{id}/checkpoints, PATCH/DELETE /records/{id}/checkpoints/{checkpoint_id}
  - Import `Checkpoint` přidán
- `leadlab/api.py` — registrován `pipeline_config_router` na `/crm/`
- `python manage.py check` → 0 issues

**Následuje:** Fáze 4 — Seed command + onboarding hook (seed_pipeline_categories management command, signal na Firm)

---

### 2026-05-03 — Fáze 4–8 dokončeny

**Fáze 4** — Seed command + onboarding hook:
- Nový soubor `crm/management/commands/seed_pipeline_categories.py`: vytváří 3 výchozí kategorie (Příležitosti / Realizace / Správa) se stages a field konfigurací; `seed_for_firm(firm)` helper bezpečně re-entrantní (get_or_create)
- `firms/api.py` `create_firm` — volá `seed_for_firm(firm)` v rámci stávající transakce po vytvoření firmy

**Fáze 5** — Frontend stores + API klient:
- Nový soubor `frontend-spa/src/stores/pipeline.ts`: Pinia store s `categories`, `allStages`; CRUD pro Category a Stage; helpers `getStageProgress()` a `getSlaColor()`; `handleCategoryUpdated()` pro WS
- `frontend-spa/src/stores/records.ts`: `RecordOut` a `RecordIn` rozšířeny o pipeline pole; `RecordFilters` o `category_id`, `stage_id`, `parent_id`; `fetchRecords` přenáší nové filtry

**Fáze 6** — Settings UI:
- Nový soubor `frontend-spa/src/views/PipelineSettingsView.vue`: dvoupanelové rozložení (kategorie vlevo, stages+fields vpravo); inline editace názvů; color picker; přidání/mazání kategorií a stages; potvrzovací dialogy pro mazání
- Route `/app/settings/pipeline` přidána do `router/index.ts`
- Tlačítko "Pipeline" v SettingsView naviguje na novou view

**Fáze 7** — RecordsView + RecordDetailView:
- `RecordsView.vue`: import `usePipelineStore`; category selector v hlavičce; `filterCategoryId`/`filterStageId`; `leadsByStage` computed; stage-based kanban (barevné sloupce dle stages); watch `category_id` query param; načítání kategorií v onMounted
- `RecordDetailView.vue`: opraven `store.currentLead` → `store.currentRecord` (21 výskytů); import `usePipelineStore`; Checkpoints panel (load/add/toggle/delete); Stage changer (klikatelné buttony s barvami); Stage progressbar (stage-based nebo fallback status-based)

**Fáze 8** — AppShell + Router:
- `AppShell.vue`: import `usePipelineStore`; `fetchCategories()` v `onMounted`; dynamická navigace kategorií pod "Records" (barevné tečky, link na `/app/records?category_id=…`); WS event registry přejmenováno `lead.*` → `record.*`; handler `category.updated` → `pipelineStore.handleCategoryUpdated()`; eventLabel a eventIcon mapy aktualizovány

**Všechny fáze 1–8 dokončeny. ✅**

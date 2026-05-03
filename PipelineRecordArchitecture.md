# Pipeline Record Architecture

Cílem je nahradit hardcodované entity **Lead**, **Realization** a **Management**
jedním obecným modelem **PipelineRecord** řízeným dynamicky konfigurovatelnými
**kategoriemi** a **stages**.  
Projekt je ve fázi vývoje — migrace se nepřenáší, databáze se vždy vytvoří znova.

---

## Přehled fází

| # | Název | Stav |
|---|-------|------|
| 1 | Smazat Realization + Management | ⬜ |
| 2 | Přejmenovat Lead → PipelineRecord + nové modely | ✅ |
| 3 | API – Category/Stage konfigurace + Records CRUD | ⬜ |
| 4 | Seed command + onboarding hook | ⬜ |
| 5 | Frontend stores + API klient | ✅ |
| 6 | Settings UI pro správu kategorií a stages | ⬜ |
| 7 | RecordsView + RecordDetailView (vzor: LeadsView) | ✅ |
| 8 | AppShell navigace + Router update | ✅ |

---

## Odškrtávací checklist

### Fáze 1 — Smazat Realization + Management ⬜

#### Backend
- [ ] `crm/models.py` — smazat třídy `RealizationStatus`, `Realization`, `Milestone`, `ManagementType`, `ManagementStatus`, `Management`
- [ ] `crm/models.py` → `Activity` — smazat FK pole `realization` a `management` + indexy
- [ ] `crm/models.py` → `Task` — smazat FK pole `realization` a `management`
- [ ] `crm/models.py` → `Document` — smazat FK pole `realization` a `management` + indexy
- [ ] Smazat `crm/realization_api.py`
- [ ] Smazat `crm/management_api.py`
- [ ] `leadlab/api.py` — odstranit importy a `add_router` pro `realization_router` a `management_router`
- [ ] `crm/api.py` — smazat importy `Management`, `Realization`; smazat endpointy `realization_metrics`, `sla_compliance`; smazat realization/management větve v action hubu; vyčistit `_task_out` od realization/management polí; vyčistit voice memo endpoint; vyčistit profitability endpoint
- [ ] `crm/tasks.py` — smazat `_action_create_realization`, `_action_create_management` a jejich volání; vyčistit weekly digest od realization/SLA stats
- [ ] `crm/automations_api.py` — smazat šablony odkazující na realization/management
- [ ] `crm/streamline/tools.py` — smazat `realization`/`management` parametry v tool schématech (řádky 1347-1348, 2071-2092)
- [ ] `crm/documents_api.py` — smazat `realization_id`/`management_id` parametry a větve; vyčistit importy a `DocumentOut` schéma
- [ ] Smazat všechny migrace v `crm/migrations/` (kromě `__init__.py`), spustit `makemigrations`

#### Frontend
- [ ] Smazat `frontend-spa/src/views/RealizationsView.vue`
- [ ] Smazat `frontend-spa/src/views/RealizationDetailView.vue`
- [ ] Smazat `frontend-spa/src/views/ManagementView.vue`
- [ ] Smazat `frontend-spa/src/views/ManagementDetailView.vue`
- [ ] Smazat `frontend-spa/src/stores/realizations.ts`
- [ ] Smazat `frontend-spa/src/stores/management.ts`
- [ ] `router/index.ts` — smazat routes `/realizations`, `/realizations/:id`, `/management`, `/management/:id`
- [ ] `AppShell.vue` — smazat WS handlery `realization.*` a `management.*`; smazat nav položky Realizace + Správa; smazat `WrenchScrewdriverIcon` a `ShieldExclamationIcon` imports (pokud jsou jen pro tyto nav položky)

---

### Fáze 2 — Přejmenovat Lead → PipelineRecord + nové modely ⬜

#### Přejmenování Lead → PipelineRecord (backend)
- [ ] `crm/models.py` — přejmenovat třídu `Lead` → `PipelineRecord`; přejmenovat `LeadStatus` → `RecordStatus`, `LeadSource` → `RecordSource`
- [ ] `crm/models.py` → `Activity.lead` FK → přejmenovat na `record`, `related_name='activities'`
- [ ] `crm/models.py` → `Task.lead` FK → přejmenovat na `record`
- [ ] `crm/models.py` → `Document.lead` FK → přejmenovat na `record`
- [ ] `crm/api.py` — přejmenovat `Lead*` schémata → `Record*`; endpoint `/leads` → `/records`; importy; WS event klíče `lead.*` → `record.*`
- [ ] `crm/tasks.py` — přejmenovat kontextové proměnné a importy Lead→PipelineRecord
- [ ] `crm/streamline/tools.py` — přejmenovat `lead_id` → `record_id` v parametrech
- [ ] `crm/documents_api.py` — přejmenovat `lead_id` → `record_id`
- [ ] `crm/admin.py` — přejmenovat `LeadAdmin` → `PipelineRecordAdmin`
- [ ] `crm/events.py` — přejmenovat event strings `lead.*` → `record.*`

#### Přejmenování Lead → PipelineRecord (frontend)
- [ ] Přejmenovat `stores/leads.ts` → `stores/records.ts`; `useLeadsStore` → `useRecordsStore`; `LeadOut`→`RecordOut`; API endpoint `/leads` → `/records`
- [ ] Přejmenovat `LeadsView.vue` → `RecordsView.vue` (zatím jen rename, adaptace v Fázi 7)
- [ ] Přejmenovat `LeadDetailView.vue` → `RecordDetailView.vue` (zatím jen rename, adaptace v Fázi 7)
- [ ] `router/index.ts` — paths `/opportunities` → `/records`, `/opportunities/:id` → `/records/:id`
- [ ] `AppShell.vue` — WS handlery `lead.*` → `record.*`; nav položka Příležitosti → Records; store reference
- [ ] `composables/useI18n.ts` — přejmenovat i18n klíče `leads.*` → `records.*`

#### Nové modely v `crm/models.py`
- [ ] **`Category`** — `id` UUID PK, `firm` FK (TenantModel), `name`, `slug` (auto), `icon`, `color`, `order`, `is_active`, `created_at`; `Meta: unique_together(firm, slug)`
- [ ] **`Stage`** — `id` UUID PK, `category` FK→Category CASCADE, `name`, `label`, `color`, `order`, `is_terminal`, `is_won`, `created_at`; `Meta: unique_together(category, order)`
- [ ] **`CategoryField`** — `id` UUID PK, `category` FK→Category CASCADE, `field_key` (choices), `is_visible`, `is_required`, `order`; `Meta: unique_together(category, field_key)`
- [ ] **`Checkpoint`** — `id` UUID PK, `record` FK→PipelineRecord CASCADE, `name`, `date`, `is_completed`, `description`, `created_at`; `SoftDeleteMixin`
- [ ] `PipelineRecord` — přidat pole `category` FK→Category nullable, `current_stage` FK→Stage nullable, `parent` FK→self nullable, `start_date`, `end_date`, `expires_at`, `notes`, `extra_data` JSONField

#### Migrace
- [ ] Smazat celý obsah `crm/migrations/` kromě `__init__.py`
- [ ] `./manage.py makemigrations crm`
- [ ] `./manage.py migrate`

---

### Fáze 3 — API ⬜

#### `crm/pipeline_config_api.py` (nový soubor)
- [ ] `GET /categories` — list per firm
- [ ] `POST /categories` — vyžaduje role owner/admin
- [ ] `PATCH /categories/{id}` — rename, color, icon, order, is_active
- [ ] `DELETE /categories/{id}` — 409 pokud existují records
- [ ] `GET /categories/{id}/stages`
- [ ] `POST /categories/{id}/stages`
- [ ] `PATCH /categories/{id}/stages/{stage_id}`
- [ ] `DELETE /categories/{id}/stages/{stage_id}` — 409 pokud jsou records s touto stage
- [ ] `GET /categories/{id}/fields`
- [ ] `POST/PATCH/DELETE /categories/{id}/fields/{field_key}`

#### `crm/records_api.py` (nový soubor — přejmenovaný a rozšířený lead sekce)
- [ ] `RecordOut` schéma s `stage_progress`, `sla_color`, `checkpoints`
- [ ] `GET /records` — filtry: category_id, stage_id, assigned_to_id, customer_id, parent_id, sort, pagination
- [ ] `POST /records`
- [ ] `GET /records/{id}`
- [ ] `PATCH /records/{id}`
- [ ] `DELETE /records/{id}` → soft delete
- [ ] `GET /records/{id}/activities`
- [ ] `GET /records/{id}/tasks`
- [ ] `GET /records/{id}/documents`
- [ ] `GET /records/{id}/checkpoints`
- [ ] `POST /records/{id}/checkpoints`
- [ ] `PATCH /records/{id}/checkpoints/{checkpoint_id}`
- [ ] `DELETE /records/{id}/checkpoints/{checkpoint_id}`

#### `leadlab/api.py`
- [ ] Registrovat `pipeline_config_router` a `records_router`
- [ ] Odebrat starý lead router

#### WebSocket events (`crm/events.py`)
- [ ] `category.updated`, `record.created`, `record.updated`, `record.deleted`

---

### Fáze 4 — Seed command + onboarding hook ⬜

- [ ] `crm/management/commands/seed_pipeline_categories.py` — vytvoří 3 výchozí kategorie (Příležitosti, Realizace, Správa) s odpovídajícími stages pro danou firmu
- [ ] `firms/api.py` nebo signal `post_save` na Firm — zavolat seed command při vytvoření nové firmy

---

### Fáze 5 — Frontend stores + API klient ⬜

- [ ] `frontend-spa/src/stores/pipeline.ts` — Pinia store: `categories`, `stages`, `records`, `currentRecord`; helpers `getStageProgress()`, `getSlaColor()`
- [ ] `frontend-spa/src/api/index.ts` — přidat volání pro `/api/v1/crm/categories`, `/api/v1/crm/records`, checkpoints

---

### Fáze 6 — Settings UI pro správu kategorií a stages ⬜

- [ ] Nová sekce nebo tab v SettingsView.vue pro správu pipeline
- [ ] Dvoupanelové rozložení: vlevo seznam kategorií (drag-and-drop), vpravo editace stages a polí
- [ ] Route `/app/settings/pipeline`

---

### Fáze 7 — RecordsView + RecordDetailView ⬜

- [ ] `RecordsView.vue` — vzor z `LeadsView.vue`; výběr kategorie v hlavičce; dynamické kanban sloupce; `useListView` composable reuse
- [ ] `RecordDetailView.vue` — vzor z `LeadDetailView.vue`; stage changer; stage progressbar; Checkpoints panel; podmíněné sekce dle CategoryField

---

### Fáze 8 — AppShell + Router ⬜

- [ ] `router/index.ts` — routes `/app/records` → `RecordsView`, `/app/records/:id` → `RecordDetailView`
- [ ] `AppShell.vue` — dynamická navigace kategorií z pipeline store; WS handlery `record.*`, `category.updated`

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

*(průběh implementace bude zaznamenáván níže)*

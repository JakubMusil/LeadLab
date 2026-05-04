# Cleanup: Přechod z Leads na Records

Tento soubor sleduje postup čištění všech zbývajících závislostí a zmínek, které stále pracují se starým termínem "lead" místo "record".

---

## Přehled změn

### 🔴 Kritické bugy (funkční breakage)
- [x] **BE-1** `crm/api.py` – `create_activity`: `ActivityIn` má `record_id`, ale funkce čte `payload.lead_id` (AttributeError za runtime) → opravit na `record_id`
- [x] **BE-2** `crm/api.py` – `upload_file_blobs`: endpoint přijímá `lead_id`, frontend posílá `record_id` (broken inline file upload) → přidat `record_id` parametr

### 🗑️ Smazat orphaned soubory
- [x] **DEL-1** Smazat `frontend-spa/src/views/LeadsView.vue` (router již nepoužívá, nahrazen `RecordsView.vue`)
- [x] **DEL-2** Smazat `frontend-spa/src/views/LeadDetailView.vue` (router již nepoužívá, nahrazen `RecordDetailView.vue`)
- [x] **DEL-3** Smazat `frontend-spa/src/stores/leads.ts` (nahrazen `records.ts`)
- [x] **DEL-4** Smazat `frontend-spa/src/stores/__tests__/leads.spec.ts` (testy smazaného store)
- [x] **DEL-5** Smazat `frontend-spa/src/views/__tests__/LeadsView.spec.ts` (testy smazaného view)

### 🔧 Interní proměnné a komentáře ve Vue views
- [x] **FE-1** `RecordsView.vue` – přejmenovat lokální proměnné `editingLead`, `contextLead`, `draggingLead` → `editingRecord`, `contextRecord`, `draggingRecord`; opravit komentáře
- [x] **FE-2** `RecordDetailView.vue` – přejmenovat lokální `lead` → `record`; opravit komentáře a aria-labels (`edit-lead-title` → `edit-record-title`); opravit i18n klíče
- [x] **FE-3** `AppShell.vue` – přejmenovat lokální `lead` → `record` ve WS handlerech; opravit komentáře

### 🔧 Komponenty – entityType union a prop typy
- [x] **FE-4** `ActivityTimeline.vue` – odebrat `'lead'` z `entityType` prop union; odstranit mrtvou větev `entityType === 'lead'`
- [x] **FE-5** `CommandPalette.vue` – kategorie `'lead'` → `'record'`; description `"Lead · …"` → `"Record · …"`
- [x] **FE-6** `TimerContextModal.vue` – `entityType: 'lead'` → `'record'`; opravit URL `/api/v1/crm/leads?` → `/api/v1/crm/opportunities?`; opravit label
- [x] **FE-7** `EntitySidebarActionPicker.vue` – odebrat `'lead'` z entityType union
- [x] **FE-8** `StreamlineCreateModal.vue` – odebrat `'lead'` z entityType union

### 🔧 Stores a composables
- [x] **FE-9** `stores/timer.ts` – `entityType: 'lead'` → `'record'`; podmínka `=== 'lead'` → `=== 'record'`
- [x] **FE-10** `LeadScoreBadge.vue` – přejmenovat na `RecordScoreBadge.vue`; opravit importy v `RecordsView.vue`

### 🔧 Zákaznický přehled
- [x] **FE-11** `CustomerDetailView.vue` – lokální `interface LeadOut` → importovat `RecordOut`; `linkedLeads` → `linkedRecords`

### 🌐 i18n lokalizace
- [x] **I18N-1** Opravit user-visible "lead" texty v hodnotách lokalizací (cs/en/de/pl): "Vyberte lead…" → "Vyberte záznam…", "leadField" → "recordField" atd.
- [x] **I18N-2** Přejmenovat namespace `leadDetail.*` → `recordDetail.*` ve všech 4 locale souborech + aktualizovat všechny komponenty používající tyto klíče

### 🔧 Backend Python – interní názvy
- [x] **BE-3** `crm/api.py` – přejmenovat interní proměnné `lead` → `record` uvnitř endpoint funkcí; přejmenovat helper funkce `_compute_lead_score` → `_compute_record_score`, `_build_lead_automation_context` → `_build_record_automation_context`
- [x] **BE-4** `crm/integrations_api.py` – lokální proměnné `lead` → `record`; komentáře
- [x] **BE-5** `crm/streamline/tools.py` – lokální `lead` → `record`; dict klíče `lead_id`/`lead_title` v interních contextech
- [x] **BE-6** `crm/automations_api.py` – komentáře a popisné texty
- [x] **BE-7** `crm/models.py` – `AutomationTrigger.LEAD_CREATED` → `RECORD_CREATED` (+ datová migrace)

### 🧪 Testy
- [x] **TEST-1** `crm/tests.py` – přejmenovat `test_patch_lead_title`, `self.lead` → `self.record`
- [x] **TEST-2** `e2e/tests/lead-lifecycle.spec.ts`, `lead-timeline.spec.ts` – aktualizovat URL a selektory

### 🔌 Pluginy
- [x] **PLUG-1** `frontend-spa/src/plugins/*.ts` – permissions `'leads:read'/'leads:write'` → `'records:read'/'records:write'`; popisné texty

---

## Prioritizace

| Priorita | ID | Popis |
|---|---|---|
| 1 🔴 | BE-1, BE-2 | Funkční bugy – aktivity a file upload |
| 2 🗑️ | DEL-1..5 | Smazat orphaned soubory |
| 3 🔧 | FE-1..3 | Interní vars ve views |
| 4 🔧 | FE-4..9 | Komponenty – entityType unions |
| 5 🔧 | FE-10..11 | ScoreBadge rename, CustomerDetail |
| 6 🌐 | I18N-1..2 | Lokalizace |
| 7 🔧 | BE-3..7 | Backend Python cleanup |
| 8 🧪 | TEST-1..2 | Testy |
| 9 🔌 | PLUG-1 | Plugin metadata |

---

## Průběh práce

### Aktuální stav

#### ✅ Dokončeno v předchozích sessions
- BE-1: `create_activity` opravena na `payload.record_id` ✅
- BE-2: `upload_file_blobs` akceptuje `record_id` ✅
- DEL-1..5: Smazány všechny orphaned soubory (LeadsView, LeadDetailView, leads.ts, atd.) ✅
- FE-1: `editingLead`, `contextLead`, `draggingLead` → `editingRecord`, `contextRecord`, `draggingRecord` ✅
- FE-2: `RecordDetailView.vue` – lokální `lead` → `record` ✅
- FE-3: `AppShell.vue` – lokální `lead` → `record` v WS handlerech ✅
- FE-4: `ActivityTimeline.vue` – odstraněna větev `entityType === 'lead'` ✅
- FE-7: `EntitySidebarActionPicker.vue` – `'lead'` odebráno z entityType union ✅
- FE-8: `StreamlineCreateModal.vue` – `'lead'` odebráno z entityType union ✅
- FE-9: `stores/timer.ts` – `entityType: 'lead'` → `'record'` ✅

#### ✅ Dokončeno v této session (2026-05-04)
- **PLUG-1**: `plugins/index.ts`, `slackNotifications.ts`, `voip.ts`, `emailSequences.ts` – `leads:read/write` → `records:read/write` ✅
- **FE-5**: `CommandPalette.vue` – `lead-${l.id}` → `record-${l.id}` ✅
- **FE-10**: `LeadScoreBadge.vue` → `RecordScoreBadge.vue` (nový soubor, starý smazán, importy aktualizovány) ✅
- **FE-11**: `CustomerDetailView.vue` – `interface LeadOut` → `RecordOut`, `linkedLeads` → `linkedRecords`, template aktualizován ✅
- **BE-3**: `_compute_lead_score` → `_compute_record_score`, `_build_lead_automation_context` → `_build_record_automation_context` v `crm/api.py` ✅
- **BE-4**: `crm/integrations_api.py` – `for lead in qs.iterator()` → `for record in qs.iterator()` ✅
- **BE-5**: `crm/streamline/tools.py` – lokální `lead` → `record`; opravena chyba `getattr(activity, "lead", None)` → `activity.record` a `lead=lead` → `record=record` v `Task.objects.create()` ✅
- **BE-6**: `crm/automations_api.py` – popisné texty updated ("lead" → "record") ✅
- **BE-7**: `AutomationTrigger.LEAD_CREATED` → `RECORD_CREATED` v `models.py` + datová migrace `0004_rename_lead_created_trigger.py` + `api.py` a `automations_api.py` aktualizovány ✅
- **TEST-1**: `test_patch_lead_title` → `test_patch_record_title`, `self.lead` → `self.record`, třída `LeadUpdateAPITest` → `RecordUpdateAPITest` ✅
- **I18N-1**: Opraveny user-visible "lead" texty v hodnotách lokalizací (cs/en/de/pl): `selectLead`, `leadField`, `leadRequired`, `triggerLeadCreated`, `triggerLeadStatusChanged`, `triggerInactiveLead`, `leadFromTrigger`, `leadStatus`, `leadSource` ✅
- **I18N-2**: Přejmenován namespace `leadDetail.*` → `recordDetail.*` ve všech 4 locale souborech + aktualizovány všechny komponenty (220+ výskytů): `ActivityTimeline.vue`, `ActivityEditModal.vue`, `StreamlineFilterDropdown.vue`, `EntitySidebarActionPicker.vue`, `StreamlineCreateModal.vue`, `ProposalBuilderView.vue`, `RecordDetailView.vue` ✅

#### ⏳ Zbývá
- **TEST-2**: `e2e/tests/lead-lifecycle.spec.ts`, `lead-timeline.spec.ts` – soubory neexistují, není co měnit ✅ (n/a)

---

### Stav po dokončení
🟢 Všechny položky cleanup.md jsou **dokončeny** (TEST-2 je n/a – soubory neexistují).

#### Shrnutí co bylo uděláno:
1. Opraveny kritické BE bugy (BE-1, BE-2) – v předchozích sessions
2. Smazány orphaned soubory (DEL-1..5) – v předchozích sessions
3. Přejmenování interních proměnných ve views (FE-1..3) – v předchozích sessions
4. Cleanup entityType unions (FE-4..9) – v předchozích sessions
5. Plugin permissions `leads:*` → `records:*` (PLUG-1)
6. CommandPalette ID `lead-*` → `record-*` (FE-5)
7. LeadScoreBadge → RecordScoreBadge (FE-10)
8. CustomerDetailView linkedLeads → linkedRecords (FE-11)
9. Backend helper funkce přejmenovány (BE-3)
10. Backend local vars v integrations_api.py, streamline/tools.py, automations_api.py (BE-4..6)
11. LEAD_CREATED → RECORD_CREATED + datová migrace (BE-7)
12. Tests: self.lead → self.record, přejmenování třídy/metody (TEST-1)
13. I18N: leadDetail → recordDetail namespace (I18N-2)
14. I18N: user-visible "lead" texty → "record/příležitost/záznam" (I18N-1)

---

_Soubor aktualizován: 2026-05-04_

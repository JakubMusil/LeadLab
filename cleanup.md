# Cleanup: Přechod z Leads na Records

Tento soubor sleduje postup čištění všech zbývajících závislostí a zmínek, které stále pracují se starým termínem "lead" místo "record".

---

## Přehled změn

### 🔴 Kritické bugy (funkční breakage)
- [ ] **BE-1** `crm/api.py` – `create_activity`: `ActivityIn` má `record_id`, ale funkce čte `payload.lead_id` (AttributeError za runtime) → opravit na `record_id`
- [ ] **BE-2** `crm/api.py` – `upload_file_blobs`: endpoint přijímá `lead_id`, frontend posílá `record_id` (broken inline file upload) → přidat `record_id` parametr

### 🗑️ Smazat orphaned soubory
- [ ] **DEL-1** Smazat `frontend-spa/src/views/LeadsView.vue` (router již nepoužívá, nahrazen `RecordsView.vue`)
- [ ] **DEL-2** Smazat `frontend-spa/src/views/LeadDetailView.vue` (router již nepoužívá, nahrazen `RecordDetailView.vue`)
- [ ] **DEL-3** Smazat `frontend-spa/src/stores/leads.ts` (nahrazen `records.ts`)
- [ ] **DEL-4** Smazat `frontend-spa/src/stores/__tests__/leads.spec.ts` (testy smazaného store)
- [ ] **DEL-5** Smazat `frontend-spa/src/views/__tests__/LeadsView.spec.ts` (testy smazaného view)

### 🔧 Interní proměnné a komentáře ve Vue views
- [ ] **FE-1** `RecordsView.vue` – přejmenovat lokální proměnné `editingLead`, `contextLead`, `draggingLead` → `editingRecord`, `contextRecord`, `draggingRecord`; opravit komentáře
- [ ] **FE-2** `RecordDetailView.vue` – přejmenovat lokální `lead` → `record`; opravit komentáře a aria-labels (`edit-lead-title` → `edit-record-title`); opravit i18n klíče
- [ ] **FE-3** `AppShell.vue` – přejmenovat lokální `lead` → `record` ve WS handlerech; opravit komentáře

### 🔧 Komponenty – entityType union a prop typy
- [ ] **FE-4** `ActivityTimeline.vue` – odebrat `'lead'` z `entityType` prop union; odstranit mrtvou větev `entityType === 'lead'`
- [ ] **FE-5** `CommandPalette.vue` – kategorie `'lead'` → `'record'`; description `"Lead · …"` → `"Record · …"`
- [ ] **FE-6** `TimerContextModal.vue` – `entityType: 'lead'` → `'record'`; opravit URL `/api/v1/crm/leads?` → `/api/v1/crm/opportunities?`; opravit label
- [ ] **FE-7** `EntitySidebarActionPicker.vue` – odebrat `'lead'` z entityType union
- [ ] **FE-8** `StreamlineCreateModal.vue` – odebrat `'lead'` z entityType union

### 🔧 Stores a composables
- [ ] **FE-9** `stores/timer.ts` – `entityType: 'lead'` → `'record'`; podmínka `=== 'lead'` → `=== 'record'`
- [ ] **FE-10** `LeadScoreBadge.vue` – přejmenovat na `RecordScoreBadge.vue`; opravit importy v `RecordsView.vue`

### 🔧 Zákaznický přehled
- [ ] **FE-11** `CustomerDetailView.vue` – lokální `interface LeadOut` → importovat `RecordOut`; `linkedLeads` → `linkedRecords`

### 🌐 i18n lokalizace
- [ ] **I18N-1** Opravit user-visible "lead" texty v hodnotách lokalizací (cs/en/de/pl): "Vyberte lead…" → "Vyberte záznam…", "leadField" → "recordField" atd.
- [ ] **I18N-2** Přejmenovat namespace `leadDetail.*` → `recordDetail.*` ve všech 4 locale souborech + aktualizovat všechny komponenty používající tyto klíče

### 🔧 Backend Python – interní názvy
- [ ] **BE-3** `crm/api.py` – přejmenovat interní proměnné `lead` → `record` uvnitř endpoint funkcí; přejmenovat helper funkce `_compute_lead_score` → `_compute_record_score`, `_build_lead_automation_context` → `_build_record_automation_context`
- [ ] **BE-4** `crm/integrations_api.py` – lokální proměnné `lead` → `record`; komentáře
- [ ] **BE-5** `crm/streamline/tools.py` – lokální `lead` → `record`; dict klíče `lead_id`/`lead_title` v interních contextech
- [ ] **BE-6** `crm/automations_api.py` – komentáře a popisné texty
- [ ] **BE-7** `crm/models.py` – `AutomationTrigger.LEAD_CREATED` → `RECORD_CREATED` (+ datová migrace)

### 🧪 Testy
- [ ] **TEST-1** `crm/tests.py` – přejmenovat `test_patch_lead_title`, `self.lead` → `self.record`
- [ ] **TEST-2** `e2e/tests/lead-lifecycle.spec.ts`, `lead-timeline.spec.ts` – aktualizovat URL a selektory

### 🔌 Pluginy
- [ ] **PLUG-1** `frontend-spa/src/plugins/*.ts` – permissions `'leads:read'/'leads:write'` → `'records:read'/'records:write'`; popisné texty

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
🔄 Zahajuji – vytvořen cleanup.md, začínám s BE-1 (kritický bug)

---

_Soubor aktualizován: průběžně_

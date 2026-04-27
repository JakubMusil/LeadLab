# Task Enhancement Goals — Freelo-Inspired Roadmap

Tento dokument rozděluje požadované úpravy systému tasků do logických, postupně implementovatelných fází.
Inspirace: SaaS aplikace [Freelo](https://app.freelo.io) — propracovaný task management s timeline, komentáři, přílohami, podtasky, provazováním a automatizacemi.

---

## Přehled požadavků

| # | Požadavek | Složitost |
|---|-----------|-----------|
| 1 | Task timeline — chronologický feed (komentáře + přílohy + události) | Střední |
| 2 | Tasky nezávislé na Leadu (volitelná vazba na Lead / Nabídku / Zákazníka) | Střední |
| 3 | Podtasky (hierarchie) | Střední |
| 4 | Řetězení tasků (follow-up, závislosti) | Nízká (základ existuje) |
| 5 | Pravidla pro automatické vytváření tasků | Střední (backend existuje) |
| 6 | Priorita, tagy, Kanban pohled | Nízká–Střední |

---

## Fáze 1 — Flexibilní task entita (odpojení od Leadu)

**Cíl:** Task nemusí být nutně vázán na Lead. Může být vázán na Proposal, Customer, nebo existovat samostatně.

### Backend
- `Task.lead` — změnit z povinného FK na `null=True, blank=True`
- Přidat `Task.proposal` — nullable FK na `Proposal`
- Přidat `Task.customer` — nullable FK na `Customer`
- Přidat `Task.parent_task` — nullable self-FK pro podporu podtasků (příprava pro Fázi 3)
- Přidat `Task.priority` — CharField s volbami `low / medium / high / urgent` (default: `medium`)
- Aktualizovat `TaskOut` schema: nová pole `proposal_id`, `customer_id`, `parent_task_id`, `priority`
- Aktualizovat `TaskIn` / `TaskUpdateIn`: `lead_id` volitelné, přidat `proposal_id`, `customer_id`, `priority`
- Aktualizovat `_task_out()` helper
- Nová DB migrace

### Frontend
- `TaskOut` interface v `stores/tasks.ts`: přidat nová pole
- `TaskIn` / `TaskUpdateIn`: `lead_id` volitelné, přidat `proposal_id`, `customer_id`, `priority`
- `TaskDetailView.vue`: zobrazit vazbu na Lead / Proposal / Customer (s RouterLink)
- `TasksView.vue`: filtrování podle entity (lead / proposal / customer / standalone)
- Formulář pro vytvoření tasku: přepínač "Vazba na:" (Lead / Nabídku / Zákazníka / Žádnou)

---

## Fáze 2 — Unified task timeline

**Cíl:** Místo oddělených sekcí "Komentáře" a "Přílohy" zobrazit jeden chronologický feed všech aktivit tasku — jako v Treelu/Freelo.

### Backend
- Nový model `TaskTimelineEntry` (nebo rozšíření `TaskComment`):
  ```
  TaskTimelineEntry:
    id, task (FK), author (FK), event_type (comment | file_upload | status_change | sub_task_added | task_created | task_assigned | task_completed), content_html (blank), metadata (JSON), created_at
  ```
- Při každé akci na tasku (vytvoření, přiřazení, dokončení, upload souboru, přidání podtasku) automaticky vytvořit `TaskTimelineEntry`
- Endpoint `GET /api/v1/crm/tasks/{id}/timeline` → vrátí seřazený feed všech typů záznamů
- Endpoint `POST /api/v1/crm/tasks/{id}/timeline` → přidat komentář (s volitelnou přílohou)
- Zachovat zpětnou kompatibilitu stávajících `/comments` a `/attachments` endpointů

### Frontend
- `TaskDetailView.vue`: nahradit sekce "Komentáře" a "Přílohy" jedním `<TaskTimeline>` komponentem
- Timeline položky podle `event_type`:
  - 💬 `comment` — rich-text komentář s @mentions, volitelné přílohy
  - 📎 `file_upload` — karta s ikonou souboru, názvem, velikostí, tlačítkem stažení/smazání
  - ✅ `task_completed` — systémová zpráva "Dokončil/a [jméno]"
  - 👤 `task_assigned` — systémová zpráva "Přiřazeno [jméno]"
  - ➕ `sub_task_added` — odkaz na podtask
- Nový komentář: RichTextEditor + drag-and-drop přílohy v jednom formuláři (jako Freelo)

---

## Fáze 3 — Podtasky

**Cíl:** Každý task může mít neomezený počet podtasků. Podtasky jsou plnohodnotné tasky s vlastní timeline.

### Backend
- Využít `Task.parent_task` FK z Fáze 1
- Endpoint `GET /api/v1/crm/tasks/{id}/subtasks` → seznam přímých podtasků
- Endpoint `POST /api/v1/crm/tasks/{id}/subtasks` → vytvořit podtask (zdědí `firm`, `lead/proposal/customer` z rodiče)
- `TaskOut` rozšířit o `subtask_count: int` a `subtasks_completed: int` (pro progress bar)
- Validace: nelze přiřadit task sám sobě jako parent; zamezit cyklickým závislostem (max hloubka 3)

### Frontend
- `TaskDetailView.vue`: sekce "Podtasky" s progress barem (X / Y hotovo)
- Inline formulář pro přidání podtasku (jen název + due_date + assignee)
- Každý podtask jako řádek s checkboxem (kompletace přímo inline) a odkazem na detail
- Breadcrumb navigace: Rodičovský task → Podtask (zobrazit v hlavičce detail view)

---

## Fáze 4 — Automatická pravidla pro vytváření tasků

**Cíl:** Definovat pravidla: "Při [triggeru] s [podmínkami] vytvoř task [název] a přiřaď ho [uživateli]."

### Stav backendu
`AutomationRule` model s triggerem `create_task` akcí **již existuje**. Chybí pouze UI a rozšíření triggerů.

### Backend
- Přidat nové `AutomationTrigger` hodnoty:
  - `task_created` — při vytvoření tasku
  - `task_completed` — při dokončení tasku (pro řetězení)
  - `proposal_accepted` — již existuje
- Akce `create_task` v `AutomationRule.actions` rozšířit o pole:
  - `title_template` — šablona s `{{lead_title}}`, `{{customer_name}}` placeholdery
  - `assign_to_user_id` — konkrétní uživatel nebo `assigned_to` (zdědí assignee triggeru)
  - `due_days_offset` — počet dní od triggeru
  - `parent_task_id` — volitelně vytvořit jako podtask

### Frontend
- Nová záložka/sekce v `SettingsView.vue` nebo samostatná `AutomationsView.vue`: "Pravidla tasků"
- Formulář pro vytvoření pravidla: výběr triggeru, podmínek (status, zdroj, hodnota), akce (název tasku, assignee, deadline)
- Seznam existujících pravidel s on/off přepínačem a logem posledních spuštění

---

## Fáze 5 — Polish & UX (Kanban, priority, tagy)

**Cíl:** Přehledné zobrazení všech tasků s možností třídění a skupinování.

### Backend
- `Task.priority` (z Fáze 1): indexovat pro filtrování
- Přidat `Task.tags` — JSONField (list of strings), jako u Leadu/Customera
- Endpoint: filtrování tasků podle `priority`, `tags`, `entity_type` (lead/proposal/customer/standalone)

### Frontend
- `TasksView.vue` — přidat přepínač zobrazení: **Seznam** / **Kanban** (grouped by `is_completed` nebo `priority`)
- Kanban sloupce: 🔴 Urgentní | 🟠 Vysoká | 🟡 Střední | ⚪ Nízká
- Nebo: 📋 Nové | 🔄 Probíhající | ✅ Dokončené
- Drag & drop mezi sloupci (kompletace, změna priority)
- Filtr panel: přiřazený, priorita, entity typ, tagy, termín
- Batch akce: vybrat více tasků → hromadné dokončení / přiřazení / smazání

---

## Doporučené pořadí implementace

```
Fáze 1 → Fáze 3 → Fáze 2 → Fáze 4 → Fáze 5
```

- **Fáze 1** je základem pro vše ostatní (flexibilní entita, podtask FK, priorita)
- **Fáze 3** navazuje přímo na datový model z Fáze 1
- **Fáze 2** zlepší UX stávajícího i nového obsahu
- **Fáze 4** má hotový backend, stačí UI
- **Fáze 5** je nadstavba pro lepší přehlednost

---

## Aktuální stav implementace

| Komponenta | Stav |
|---|---|
| `Task` model (vázaný na Lead) | ✅ Hotovo |
| `TaskComment` model + CRUD API | ✅ Hotovo |
| `TaskAttachment` model + upload API | ✅ Hotovo |
| `Task.watchers` (M2M) | ✅ Hotovo |
| `TaskDetailView.vue` (komentáře + přílohy) | ✅ Hotovo (sekce oddělené) |
| `TasksView.vue` (seznam + filtrování) | ✅ Hotovo |
| Follow-up task po dokončení | ✅ Hotovo |
| `AutomationRule` s `create_task` akcí | ✅ Backend hotovo |
| Task nezávislý na Leadu | ❌ Chybí |
| Podtasky (`parent_task` FK) | ❌ Chybí |
| Unified timeline | ❌ Chybí |
| Priorita + tagy | ❌ Chybí |
| Pravidla tasků UI | ❌ Chybí |
| Kanban pohled | ❌ Chybí |

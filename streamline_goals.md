# Streamline Goals — Sjednocení timeline modelů přes Streamline framework

> **Cíl:** Po zavedení Streamline frameworku (generická `Activity` + `StreamlineTool` registry pro
> `comment` / `call` / `meeting` / `email_*` / `status_change` / `file_upload` / `task_*` /
> `proposal_*` / `entity_change`) odstranit z `crm/models.py` modely, které dělají duplicitní práci
> vůči `Activity` + příslušnému `StreamlineTool`, a sjednotit timeline napříč celým systémem.

---

## Co si o tom myslím

Souhlasím — máš to zmapované přesně. Po tom, co jsme zavedli Streamline framework, existuje v
`crm/models.py` několik modelů, které dnes dělají duplicitní práci vůči `Activity` + příslušnému
`StreamlineTool`. Můžeme je odstranit / vyprázdnit a sjednotit přes Streamline. Je to velký úkol
(datová migrace, API, frontend), ale dává smysl ho udělat — jinak budeme mít navždy dvě paralelní
timeline implementace.

---

## 1. Modely, které jsou dnes redundantní vůči Streamline

| Redundantní model | Co dělá dnes | Streamline ekvivalent | Doporučení |
| --- | --- | --- | --- |
| `LeadAttachment` | soubor přiložený k Leadu | `FileUploadTool` (Activity) + `Document` (s lead FK) | **Smazat.** `Document` už pokrývá multi-entity přílohy, `FileUploadTool` zaloguje událost do timeline. |
| `TaskAttachment` | soubor přiložený k Tasku | `Document` (s task FK) + `FileUploadTool` | **Smazat.** Stejný argument jako `LeadAttachment`. |
| `TaskComment` | rich-text komentář k tasku (legacy) | `CommentTool` na `Activity` | **Smazat.** V kódu už je nahrazený `TaskTimelineEntry`, doteď přežíval jen pro zpětnou kompatibilitu. |
| `TaskTimelineEntry` | kompletní paralelní timeline jen pro Task | `Activity` + tooly | **Sjednotit do `Activity`.** Přidat `task` FK na `Activity`, `event_type` namapovat na `Activity.type` (= `activity_type` toolu). Tohle je hlavní zjednodušení. |
| `TaskCommentReaction` | emoji reakce na timeline entry tasku | (chybí) — viz nový `ReactionTool` níže | **Generalizovat** na `ActivityReaction` vázaný na `Activity`. |
| `TaskVoiceAttachment` | hlasová zpráva v komentáři tasku | (chybí) — viz nový `VoiceMemoTool` | **Generalizovat** přes Streamline; zatím jediný legitimní rozdíl proti `file_upload` je `duration_seconds`, který může jít do `metadata`. |
| `LeadStatusHistory` | imutabilní log status změn pro pipeline velocity | `StatusChangeTool` (`Activity` s `metadata.old_status` / `metadata.new_status` + `created_at` + `user`) | **Smazat.** `Activity` už nese vše potřebné. Velocity report přepsat nad `Activity.objects.filter(type="status_change")`. (Pozor — dnes do `LeadStatusHistory` zapisuje i `StatusChangeTool.process_action`; ten záznam je tam doslova kopií `Activity`.) |
| `TaskChecklistItem` *(částečně)* | položka checklistu | — strukturovaná data o kompletním checklistu by mohla žít v `metadata` Tasku, ale tohle je vlastní entita, ne timeline událost; **nedoporučuji rušit**. Místo toho přidat `ChecklistItemCheckedTool` pro logování zaškrtnutí do timeline. | |

**Co naopak rušit nebudu:** `Task`, `Notification`, `Project`, `TaskDependency`, `Document`,
`TaskTimeLog` / `TaskTimer` / `TimeEntry`, `Milestone` — to jsou skutečné doménové entity,
ne timeline log.

---

## 2. Streamline tooly, které je potřeba doplnit

Po odstranění výše uvedených modelů (hlavně `TaskTimelineEntry`) musíme do
`crm/streamline/tools.py` doplnit tooly pro události, které dnes pokrývá jen `TimelineEventType`:

| Nový tool | `activity_type` | Účel | Pozn. |
| --- | --- | --- | --- |
| `PriorityChangeTool` | `priority_change` | změna priority tasku | mohlo by jít i přes generický `entity_change`, ale samostatný tool má hezčí ikonu/label |
| `AssigneeChangeTool` | `assignee_change` | (pře)přiřazení tasku/leadu | side-effect: poslat notifikaci novému assignee |
| `DueDateChangeTool` | `due_date_change` | změna termínu | |
| `SubTaskAddedTool` | `sub_task_added` | přidán subtask | |
| `TaskCreatedTool` | `task_created` | vytvoření tasku | dnes není; logovat z `tasks_api.create_task` |
| `TaskArchivedTool` | `task_archived` | archivace | |
| `ApprovalRequestedTool` | `approval_requested` | spuštění schvalovacího workflow | |
| `ApprovalResolvedTool` | `approval_resolved` | accept/reject schválení | |
| `TimeLoggedTool` | `time_logged` | manuální zalogování času / stop timeru | side-effect: žádný (`TimeLog` je vlastní entita) |
| `ChecklistItemCheckedTool` | `checklist_item_checked` | zaškrtnutí položky checklistu | |
| `VoiceMemoTool` | `voice_memo` | hlasová zpráva (`url`, `duration_seconds`, volitelně `transcript`) | nahrazuje `TaskVoiceAttachment` napříč všemi entitami |
| `ReactionTool` | *není `activity_type`* | toggle emoji na existující `Activity` | implementuje se mimo `StreamlineTool` jako endpoint nad samostatným modelem `ActivityReaction(activity, user, emoji)` |

### Další tooly, které by se uživatelům hodily *(návrh nad rámec sjednocení)*

| Tool | Proč | Krátký popis |
| --- | --- | --- |
| `SmsOutTool` / `SmsInTool` | logování SMS komunikace | `to`, `from`, `content_text`, `provider_message_id` |
| `WhatsAppTool` / `ChatTool` | obdoba pro IM kanály | jednotná timeline napříč kanály |
| `MeetingScheduledTool` | doteď máme jen `meeting` (po faktu); tohle je kalendářní pozvánka | `start_at`, `end_at`, `location`, `attendees`, `ics_url` |
| `LinkTool` | uložený odkaz s OG-preview (URL k webu, dokumentu, externímu zdroji) | `url`, `title`, `description`, `thumbnail` |
| `PaymentReceivedTool` / `InvoiceSentTool` | napojení na Fakturoid/ERP | `amount`, `currency`, `invoice_id`, `due_date` |
| `SignatureRequestedTool` / `SignatureCompletedTool` | e-sign workflow proposalu/dokumentu | `document_id`, `signer_email`, `provider`, `status` |
| `ProposalViewedTool` | pasivní tracking otevření nabídky klientem | dnes `Proposal` má `viewed_at` ale není to v timeline |
| `AiSummaryTool` / `AiSuggestedActionTool` | AI shrnutí konverzace nebo doporučená další akce | `model`, `prompt_version`, `summary_text`, `suggested_action` |
| `SystemNoteTool` | obecná systémová zpráva (např. "Importováno z CSV", "Migrováno z Pipedrive") | bez user-facing composeru |
| `TagAddedTool` / `TagRemovedTool` | přidání/odebrání tagu | univerzální, uživatel vidí historii štítkování |
| `MentionTool` | samostatná aktivita "byl jsi zmíněn" (dnes je mention jen vedlejší efekt komentáře) | volitelné — možná stačí současné chování |
| `PinnedTool` / `UnpinnedTool` | zápis o pinování důležité aktivity | užitečné pro long-running leady |

---

## 3. Rozdělení do fází

Úkol je velký — doporučuji rozdělit na **6 fází**, bez breaking changes mezi nimi (vše přes
deprecation cycle).

### Fáze 0 — Příprava *(1 PR)*

- Doplnit `task` FK na `Activity` (+ index, + property `entity_type` rozšířit o `"task"`).
- Rozšířit enum `ActivityType` o všechny nové typy z tabulky výše.
- Připravit `_ENTITY_TOOLBAR["task"]` v `streamline/api.py`.
- Žádné mazání — jen rozšíření `Activity`, aby bylo kam migrovat.

### Fáze 1 — Doplnit chybějící Streamline tooly

- Implementovat všechny tooly z tabulky v sekci 2 (kromě nových-nad-rámec; ty si dej do samostatné fáze).
- `process_action` většinou no-op (jde o pouhý log). U `AssigneeChangeTool` poslat notifikaci.
- Unit testy pro každý tool (schema validace + `render_payload`).

### Fáze 2 — Migrace `LeadStatusHistory` → `Activity`

- Datová migrace: pro každý `LeadStatusHistory` záznam, který nemá odpovídající
  `Activity(type="status_change")`, vytvořit `Activity`.
- Přepsat reporty pipeline velocity nad `Activity`.
- Smazat zápis do `LeadStatusHistory` z `StatusChangeTool.process_action`.
- Označit `LeadStatusHistory` jako deprecated (nechat 1 release), pak smazat model + migraci.

### Fáze 3 — Migrace `LeadAttachment` + `TaskAttachment` → `Document`

- Datová migrace: pro každý `LeadAttachment` vytvořit `Document(lead=...)` se stejným souborem
  (file pointer move, ne copy) a `Activity file_upload`. Totéž pro `TaskAttachment`.
- Přesměrovat API endpointy (`/leads/{id}/attachments`, `/tasks/{id}/attachments`) na
  `Document` API + zachovat dočasné aliasy s deprecation hlavičkou.
- Frontend: použít existující document-list komponenty.
- Smazat modely + endpointy ve fázi 5.

### Fáze 4 — Sjednocení Task timeline (`TaskTimelineEntry` → `Activity`)

> Toto je největší krok, dělej ho samostatně.

- Datová migrace `TaskTimelineEntry` → `Activity`:
  - `event_type` → `Activity.type`
  - `content_html` → `Activity.content_text`
  - `metadata` → `Activity.metadata`
  - `author` → `Activity.user`
  - `parent_entry` → uložit jako `metadata.reply_to_id` (`Activity` nemá threading; rozhodni:
    buď přidej `parent_activity` FK, nebo řeš threading přes `metadata`).
- Migrovat `TaskCommentReaction` → nový
  `ActivityReaction(activity, user, emoji, unique_together=(activity, user, emoji))`.
- Migrovat `TaskVoiceAttachment` → `Activity voice_memo` s `metadata.duration_seconds` +
  `Document` pro samotný soubor.
- Přepsat `tasks_api.py` (timeline endpointy) tak, aby četlo `task.activities.all()`.
- Frontend: sjednotit komponenty `TaskTimeline` a `EntityActivityFeed` do jediné.
- Smazat `TaskTimelineEntry`, `TaskCommentReaction`, `TaskVoiceAttachment`, `TaskComment`
  (`TaskComment` byl už dříve nahrazený `TimelineEntry`, takže ten může spadnout v této fázi taky).

### Fáze 5 — Úklid

- Smazat deprecated modely a migrace zavedené ve fázích 2–4.
- Pročistit `crm/models.py`, signály, admin, serializéry.
- Aktualizovat dokumentaci (`docs/`, `mkdocs.yml`).
- E2E testy pro každou entitní timeline (lead, task, realization, management, customer, proposal).

### Fáze 6 *(volitelná)* — Nové tooly nad rámec sjednocení

- SMS, WhatsApp, MeetingScheduled, Link, Payment/Invoice, Signature, ProposalViewed, AiSummary,
  SystemNote, Tag…
- Každý jako samostatný malý PR; není nutné dělat všechny najednou.

---

## 4. Rizika a na co dát pozor

- **Migrace dat je nevratná** — všechny tři velké migrace (status history, attachments, task
  timeline) musí mít backup snapshot a idempotentní `RunPython` (s `reverse_code = noop` nebo
  opravdovým reverzem).
- **`TaskTimelineEntry.parent_entry` (threading)** — v `Activity` dnes není ekvivalent. Buď přidat
  `parent_activity` FK (jednoduché), nebo vědomě threading zrušit; doporučuji přidat FK.
- **`Activity` má `firm` jen přes entitu** — Task má `firm` napřímo, takže to je OK, ale ujisti se,
  že WebSocket broadcasting na firm-channel funguje stejně.
- **`StatusChangeTool` dnes v `process_action` přepisuje `lead.status`** — když smažeme
  `LeadStatusHistory`, samotná logika status změny zůstává, jen vypadne ten druhý zápis.
  Bez problémů.
- **API zpětná kompatibilita** — externí klienti (mobil, Zapier, atd.) můžou volat staré
  endpointy. Drž je naživu jako `410 Gone` alias / proxy minimálně 1 release.
- **Permissions** — `StreamlineTool` API má `auth=django_auth`; ujisti se, že tooly s
  side-effecty (např. `AssigneeChangeTool`) mají stejné kontroly oprávnění, jaké dnes mají
  dedikované endpointy v `tasks_api.py`.
- **Performance** — `Activity` se po sjednocení s tasky výrazně zvětší. Zkontroluj, že indexy
  `(task, -created_at)` a `(task, type)` se přidají ve fázi 0.
- **Auto-logging signály** — `EntityChangeTool` se spouští z `pre_save` / `post_save`. Pro `Task`
  se může začít překrývat s explicitním `PriorityChangeTool` apod. → buď vypnout auto-log na
  polích, která mají dedikovaný tool, nebo nechat oboje (může to být v pořádku, ale rozhodni
  vědomě).

---

## TL;DR

- **Smazat:** `LeadAttachment`, `TaskAttachment`, `TaskComment`, `TaskTimelineEntry`,
  `TaskCommentReaction`, `TaskVoiceAttachment`, `LeadStatusHistory`.
- **Generalizovat:** `TaskCommentReaction` → `ActivityReaction`; `TaskVoiceAttachment` →
  `voice_memo` Activity tool.
- **Doplnit Streamline tooly:** priority / assignee / due-date / subtask / task-created /
  task-archived / approval-{req,res} / time-logged / checklist-item-checked / voice-memo
  (+ reaction model bokem).
- **Bonus tooly k zvážení:** SMS, WhatsApp, MeetingScheduled, Link, Payment/Invoice, Signature,
  ProposalViewed, AiSummary, SystemNote, Tag.
- **6 fází**, každá samostatný PR, bez breaking changes mezi nimi.

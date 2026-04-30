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

**Stav backend:** ✅ Hotovo v dřívějších PR (Activity má `task` FK, tooly Phase 1
zaregistrované, `/api/v1/crm/tasks/{id}/activities` endpoint, `ActivityReaction`
model + endpoint).

**Stav frontend:** ✅ Kroky A + B hotovy v session končící 2026-04-29.

Co bylo v této session uděláno (Krok A + B z plánu „sjednocení frontendu pod
design lead detail"):

- **Krok A** — `frontend-spa/src/components/ActivityTimeline.vue`:
  - `props.entityType` rozšířen o `'task'`
  - `listUrl()` má větev `task → /api/v1/crm/tasks/{id}/activities`
  - `entityIdKey()` vrací `task_id` pro task entitu
  - filtr `task` a action-picker entry pro `task` se skryjí, když
    `entityType === 'task'` (otevřený task nemůže sám sebe vytvořit)
  - `heroIconMap` + `activityIconMap` rozšířené o všechny Phase 1 + Phase 6
    bonus tooly (priority/assignee/due-date/sub-task, time-logged,
    checklist-item-checked, voice-memo, SMS, WhatsApp, link, payment,
    invoice, signature, AI, system-note, tag, mention, pin)
- **Krok B** — `frontend-spa/src/views/TaskDetailView.vue`:
  - smazána ~390řádková legacy timeline sekce (vlastní komposer s
    `change_assignee_to` / `log_time_minutes` / `set_due_date` toggles,
    file-upload dropzone, attachment renderer, `systemEventLabel`,
    `fileTypeIcon`, `downloadAll`, sort toggle, per-entry emoji picker,
    sticky description-as-first-entry)
  - nahrazena jediným `<ActivityTimeline ref entity-type="task" :entity-id="taskId" />`
  - description editor je samostatná karta nad timeline (RichTextEditor
    pattern z `LeadDetailView`)
  - odstraněny importy `TaskTimelineEntryOut` / `TaskTimelinePostIn` /
    `TaskAttachmentOut` / `ReactionSummaryOut`; `tasksStore.fetchTimeline` /
    `createTimelineEntry` / `toggleTimelineReaction` zůstávají ve store
    (e2e testy + public link), view je nepoužívá
  - side-actions (assignee / due date) běží přes existující Edit Task
    modal; time logging přes existující stopwatch widget. Streamline tooly
    události zalogují samy přes signály
  - zachováno: subtasks, checklist, dependencies, time tracking,
    watchers, custom fields, recurrence, approval
- **Backend (potřeba pro reakce v unified ActivityTimeline):**
  - `ActivityOut` schémata (v `crm/api.py`, `realization_api.py`,
    `management_api.py`, `proposals_api.py`) mají pole `reactions: List[dict]`
  - `_activity_out(activity, requesting_user=None)` agreguje emoji reakce
    do tvaru `ReactionSummaryOut`; všechna call sites posílají `request.user`
    a queryset má `prefetch_related('reactions')` proti N+1
  - **nový endpoint** `POST /api/v1/crm/activities/{id}/reactions` (toggle,
    entity-agnostic, firm-scoped přes ownership entity v aktivitě) —
    vyřazuje potřebu per-entity reaction routes
- **`ActivityTimeline.vue` — reaction UI:**
  - inline emoji picker (👍 ❤️ 😂 😮 👏 🎉 🔥 ✅) + agregované reakce
    chip-y pod každou comment aktivitou; optimistický update z toggle
    response
  - i18n klíč `leadDetail.addReaction` ve 4 lokálech (en/cs/de/pl)

**Validace:** 48/48 activity testů + 24/24 task testů prochází; CodeQL +
code review bez nálezů.

**Co zbývá ve Fázi 4:** smazat legacy modely `TaskTimelineEntry`,
`TaskCommentReaction`, `TaskVoiceAttachment`, `TaskComment` (viz sekce
„Další kroky" níže).

### Fáze 5 — Úklid

- Smazat deprecated modely a migrace zavedené ve fázích 2–4.
- Pročistit `crm/models.py`, signály, admin, serializéry.
- Aktualizovat dokumentaci (`docs/`, `mkdocs.yml`).
- E2E testy pro každou entitní timeline (lead, task, realization, management, customer, proposal).

### Fáze 6 *(volitelná)* — Nové tooly nad rámec sjednocení

**Stav:** ✅ Implementováno (viz `crm/streamline/tools.py` + migrace
`0039_phase6_streamline_bonus_activity_types`).

Nové `ActivityType` choices a registrované `StreamlineTool` třídy:

| Tool | `activity_type` | Side-effect |
| --- | --- | --- |
| `SmsOutTool` / `SmsInTool` | `sms_out` / `sms_in` | — |
| `WhatsAppOutTool` / `WhatsAppInTool` | `whatsapp_out` / `whatsapp_in` | — |
| `ChatTool` | `chat` (s `metadata.channel`) | — |
| `MeetingScheduledTool` | `meeting_scheduled` | — |
| `LinkTool` | `link` | — |
| `PaymentReceivedTool` | `payment_received` | — |
| `InvoiceSentTool` | `invoice_sent` | — |
| `SignatureRequestedTool` / `SignatureCompletedTool` | `signature_requested` / `signature_completed` | — |
| `ProposalViewedTool` | `proposal_viewed` | stamp `Proposal.first_viewed_at` (jen poprvé) + bump `view_count` |
| `AiSummaryTool` / `AiSuggestedActionTool` | `ai_summary` / `ai_suggested_action` | — |
| `SystemNoteTool` | `system_note` | — |
| `TagAddedTool` / `TagRemovedTool` | `tag_added` / `tag_removed` | — |
| `MentionTool` | `mention` | vytvoří `Notification` pro zmíněného uživatele (event `activity.mention`) |
| `PinnedTool` / `UnpinnedTool` | `pinned` / `unpinned` | — |

Implementační poznámky:

- Většina toolů sdílí `_SimpleLogTool` helper (DRY pro `get_schema` /
  `process_action` / `render_payload` u tooltů, které jsou jen log).
- `ProposalViewedTool` je idempotentní vůči `first_viewed_at` (přepíše jen
  pokud je `NULL`), takže opakované otevření klientem přidává jen do
  `view_count`.
- `MentionTool` neposílá notifikaci, pokud je zmíněný uživatel autorem
  aktivity (stejné chování jako u `CommentTool` mention side-effectu a
  `AssigneeChangeTool`).
- Unit testy: `crm.tests.StreamlinePhase6ToolsTest` (registrace, schémata,
  render, side-effecty pro `proposal_viewed` a `mention`).

---

## Další kroky pro příští session

> **Důležitý kontext:** aplikace je stále čistě ve fázi vývoje, **nejsou
> v provozu žádná produkční data ani externí klienti**. To znamená:
>
> - **Žádná datová migrace není potřeba** — modely lze rovnou smazat / zahodit
>   sloupce, není třeba `RunPython` převádět záznamy ze starých tabulek do
>   `Activity`. Pokud existující dev data v databázi po DROPu vadí, stačí
>   `python manage.py migrate crm zero && python manage.py migrate` nebo
>   recreate DB.
> - **Žádná zpětná kompatibilita API** — endpointy lze odstranit, ne držet
>   `410 Gone` aliasy přes release. Frontend (vlastní SPA + e2e) je jediný
>   konzument; aktualizujeme oboje synchronně v jednom PR.
> - **Žádné deprecation cycles** — v plánu výše (sekce 3) jsou zmiňované „1
>   release deprecated, pak smazat" — pro nás stačí jeden PR, který smaže
>   model, endpoint, frontendovou referenci a starou migraci najednou.
>
> Tohle radikálně zjednodušuje zbývající fáze 2/3/5 i Krok C níže.

### A) Dokončit Fázi 4 — smazat legacy task timeline modely *(1 PR)*

**Stav:** ✅ Hotovo v session končící 2026-04-29.

Co bylo v této session uděláno:

1. ✅ `crm/models.py`: legacy modely (`TaskTimelineEntry`, `TaskCommentReaction`,
   `TaskVoiceAttachment`, `TaskComment`, `TaskAttachment`, `LeadAttachment`,
   `LeadStatusHistory`) byly už smazané v dřívější iteraci; migrace
   `0038_drop_legacy_attachment_comment_timeline_models.py` je v provozu.
2. ✅ `crm/api.py`: smazány legacy endpointy
   `GET/POST /api/v1/crm/tasks/{id}/timeline` a
   `POST /api/v1/crm/tasks/{id}/timeline/{entry_id}/reactions` plus jejich
   schémata (`TaskTimelineEntryOut`, `TaskTimelinePostIn`, `TimelineReactionIn`,
   `TimelineAttachmentOut`, `ReactionSummaryOut`) a privátní helpery
   (`_reactions_for_activity`, `_activity_to_timeline_out`,
   `_log_task_activity`). Helper `_log_timeline_event` zůstává (široce
   používaný napříč `tasks_api`) a je nyní self-contained — loguje rovnou
   `Activity(task=...)`.
3. ✅ `crm/streamline/tools.py` — kontrola provedena, žádný tool nezávisí
   na `TaskTimelineEntry` ani příbuzných legacy modelech.
4. ✅ `frontend-spa/src/stores/tasks.ts`: smazány typy `TaskTimelineEntryOut`,
   `TaskTimelinePostIn`, `TimelineAttachmentOut`, `ReactionSummaryOut` a
   deprecated alias `TaskAttachmentOut`; smazány metody `fetchTimeline`,
   `createTimelineEntry`, `toggleTimelineReaction` plus jejich exporty.
   `PublicTaskView` legacy timeline endpointy nepoužíval, e2e testy je
   nereferencují.
5. ✅ Migrace — `0038_drop_legacy_attachment_comment_timeline_models.py`
   pokrývá `DeleteModel` pro všechny dotčené legacy modely, žádný
   `RunPython` (dev fáze, žádná datová migrace nutná).
6. ✅ Dokumentace — `docs/` ani `mkdocs.yml` legacy timeline endpointy
   nereferencují; tento dokument aktualizován.

**Validace:** 172/172 backend testů prochází; frontend `vue-tsc` baseline
errors beze změny (pre-existing strict-null issues v nezměněných views);
frontend unit testy beze změny (66 fail / 102 pass — všechny failures
pre-existing v Team / Settings / Customers / Leads / Dashboard).

### B) Krok C — sjednotit Customer / Realization / Management / Proposal pod design lead detail *(1–4 PR)*

Plán ze session 2026-04-29 ho odložil jako kosmetiku. Všechny 4 views už
mají `<ActivityTimeline>` integrovaný; zbývá:

1. ✅ **`EntitySidebarActionPicker.vue` extrahovaný** — komponenta v
   `frontend-spa/src/components/EntitySidebarActionPicker.vue` přijímá
   `entityType` + `entityId`, načítá
   `/api/v1/streamline/entity-toolbar/{type}` a zobrazí action picker
   + form-schema-driven inputy. Submit volá generický
   `POST /api/v1/crm/activities` se správným `*_id` polem. Použito v
   `LeadDetailView` a `ManagementDetailView`.
2. **2-sloupcový layout** (timeline vlevo, sidebar vpravo, sticky) v:
   - ✅ `CustomerDetailView.vue` *(2026-04-29 session — tabs
     `Overview` / `Tasks` / `Files`, 2-col Overview s
     `EntitySidebarActionPicker`, Tasks přes `customer_id` filter,
     Files přes Document API)*
   - ✅ `RealizationDetailView.vue` *(2026-04-29 session — Overview tab
     přepsán do 2-col layoutu (`ActivityTimeline` vlevo `col-span-2` +
     sidebar s `EntitySidebarActionPicker`, popisek, milestones progress,
     customer/lead/assignee/dates karty); duplicitní separátní
     `activities` tab odstraněn; pre-existing tabs `milestones`/`tasks`/
     `proposals`/`documents` ponechány. Header zjednodušený (jen
     title + status), meta info migrováno do sidebaru.)*
   - ✅ `ManagementDetailView.vue` *(layout už existoval; přidán
     `EntitySidebarActionPicker` do toolbox sidebaru, timeline má `ref`
     pro reload po quick-action submitu)*
   - ✅ `ProposalBuilderView.vue` *(2026-04-29 session — spodní sekce
     "Activity Timeline" přepsána na 2-sloupcový grid: timeline vlevo
     (`lg:col-span-2`) s `ref="activityTimelineRef"`, vpravo
     `EntitySidebarActionPicker entity-type="proposal"`. Builder UI
     (header bar, editor, live preview) zůstal kompletně netknutý dle
     plánu. Quick-action submit reloaduje timeline přes ref.)*
3. **Sjednotit tabs** — `overview` / `tasks` / `files` / *(entity-specific)*
   tam, kde dnes nejsou. `Files` přepnout na `DocumentsView`-style
   komponenty místo per-entity custom uploaderu.
   - ✅ Customer + Realization + Management hotové.
   - Proposal — N/A: `ProposalBuilderView` má jiné UX (builder, ne detail
     view), tabs nejsou aplikovatelné. Streamline timeline je doplňkový
     panel pod editorem, což je správný shape pro builder.
4. **Inline editaci popisku** — RichTextEditor + `startEdit/save/cancel`
   pattern z `LeadDetailView` aplikovat na entity, které mají
   `description` / `description_html`.
   - Customer model `description` field nemá → krok 4 se na něj
     neaplikuje.
   - Realization má `description` (plain text) — zatím render-only;
     inline edit je nice-to-have, ne blokátor sjednocení designu.
   - Proposal má vlastní editor v builderu (Markdown body, line items,
     closing) — RichTextEditor pattern z LeadDetailView se neaplikuje,
     builder vlastní svůj save flow přes `editTitle`/`editContent`/atd.
5. **i18n** — průchod nově použitými klíči, doplnit chybějící do
   en/cs/de/pl, ověřit `node scripts/check-locales.mjs`.
   - ✅ Customer (10 klíčů) + Realization (5 klíčů) doplněno do všech
     4 lokálů (1817 klíčů × 4 jazyky, locale-checker passes).
   - ✅ Proposal — žádné nové klíče potřeba (reuse
     `leadDetail.tabActivities` pro timeline header, sidebar action
     picker si načítá labely z `entity-toolbar` API).

**Stav po session 2026-04-29 (PR `copilot/add-customer-realization-proposal-prs`):**
✅ Customer + Realization + Proposal **hotové**. Krok C je tímto PR
**uzavřený**.

### Co dál po Kroku C

Stav po session 2026-04-29 (druhá iterace):

1. ✅ **Fáze 2 backend úklid** (`LeadStatusHistory`) — již proběhlo
   v migraci `0038_drop_legacy_attachment_comment_timeline_models.py`.
   Žádné runtime referencie nezbyly; jen historický log v této markdown.
2. ✅ **Fáze 3 backend úklid** (`LeadAttachment` + `TaskAttachment`) —
   také proběhlo v migraci `0038`. Pouze legacy upload-path helpers
   (`_attachment_upload_to`, `_task_attachment_upload_to`,
   `_voice_attachment_upload_to`) v `crm/models.py` zůstaly s docstring
   *"kept for migrations"* — historické migrace 0002/0014/0018 je
   importují, takže smazat nelze.
3. ✅ **Inline `description` edit pro Realization** *(2026-04-29 session
   druhá iterace)* — `RealizationDetailView.vue` Description sidebar
   karta umí inline edit:
   - State: `editingDescription`, `descriptionDraft`, `savingDescription`
     + `startEditDescription` / `saveDescription` / `cancelEditDescription`.
   - Edit button (… vpravo) → textarea (4 rows, resize-y) + Save/Cancel.
   - Když je `description` prázdný, klik na placeholder spustí editaci.
   - Plain text (textarea, ne RichTextEditor) — odpovídá datovému modelu
     (Realization `description` je plain string, ne HTML — na rozdíl od
     `Lead.description`).
   - Save přes `store.updateRealization(id, { description })`, success
     toast `realizations.updated`, error `realizations.failedToUpdate`.
   - i18n: 2 nové klíče `realizations.edit` + `realizations.failedToUpdate`
     × 4 lokály (en/cs/de/pl).
4. ✅ **Frontend dead-code cleanup** *(2026-04-29 session druhá iterace)*
   — odstraněny nepoužívané `fetchTaskAttachments` /
   `uploadTaskAttachment` / `deleteTaskAttachment` + interface
   `TaskDocumentOut` z `frontend-spa/src/stores/tasks.ts`. Šlo o legacy
   alias k `tasks/{id}/documents` Document API; nikde se nikdy
   nezavolaly.
5. ✅ **Fáze 6 — nové tooly nad rámec** — již implementováno v migraci
   `0039_phase6_streamline_bonus_activity_types`
   (`ProposalViewedTool`, `AiSummaryTool`, `AiSuggestedActionTool`,
   `MentionTool`, `SystemNoteTool`, `TagAddedTool`, `TagRemovedTool`,
   `PinnedTool`, `UnpinnedTool`, `LinkTool`, `PaymentReceivedTool`,
   `InvoiceSentTool`, `SignatureRequestedTool`, `SignatureCompletedTool`).
   Viz sekce 5.2 níže.

### Co dál po této session

Backend i frontend Streamline systému jsou **kompletně sjednocené** —
všechny entity (lead, customer, realization, management, proposal, task)
mají jednotný `Activity` log + `EntitySidebarActionPicker` + responzivní
2-col layout. Reálné navazující práce už nejsou v tématu Streamline,
ale v okolních oblastech:

1. **E2E testy timeline UX** *(sekce 4.10 — Fáze 5 follow-up)* — pro
   každou entitní timeline (lead, task, realization, management,
   customer, proposal) ověřit happy-path s Cypress/Playwright. Zatím
   pokryté pouze unit testy v `crm/tests.py`.
2. ✅ **Odstranit baseline `vue-tsc` errory** *(2026-04-29 session třetí
   iterace)* — `RealizationDetailView.vue` 3 errory + `stores/realizations.ts`
   10 errorů + `stores/management.ts` 10 errorů. Celkem **−23 errorů**
   (z 57 unikátních na 34). Konkrétně:
   - `RealizationDetailView.vue`: odstraněn redundantní 3. arg
     `{ headers: firmHeader() }` z `api.post`/`api.patch`/`api.delete`
     volání (řádky 110, 135, 149). Odstraněn nepoužitý `firmHeader()`
     helper, `firmStore` ref a import `useFirmStore`. Firm header se
     nastavuje globálně přes interceptor v `src/api/index.ts` —
     `getFirmId()` čte z `localStorage` a přidává `X-Firm-ID` ke všem
     `request<T>()` voláním. Žádná runtime regrese.
   - `stores/realizations.ts` + `stores/management.ts`:
     `extractErrorMessage(x)` calls (jen 1 arg) v `console.error`
     blocích → přidán fallback `''` jako 2. arg podle konvence
     ze `stores/customers.ts`. Jen log statements, žádná runtime změna.
   - Vitest baseline: 66 failed / 102 passed test count beze změny
     (preexisting failures jsou nezávislé — i18n/messages compile
     errors v testech).
3. **Pokračování baseline `vue-tsc` cleanup** *(zbývá 13 unikátních errorů)*:
   - ✅ **`GanttView.vue` ambient module** *(2026-04-29 čtvrtá iterace)* —
     do `env.d.ts` přidán `declare module 'frappe-gantt'`. Package
     ships jen ES bundle bez `.d.ts`, importujeme ho jen dynamicky
     s `as any` cast. Snižuje 1 error (TS7016).
   - ✅ **Test fixture drift** *(2026-04-29 čtvrtá iterace)* — doplněna
     chybějící pole do mock objektů ve 4 spec souborech:
     - `auth.spec.ts`: `is_superuser: false`.
     - `leads.spec.ts`: `created_by_id: null`, `created_by_name: null`.
     - `tasks.spec.ts`: `recurrence`, `recurrence_parent_id`,
       `approval_required`, `approval_status`, `approval_requested_from_id`,
       `approval_requested_from_name`, `approval_note`, `custom_fields`.
     - `customers.spec.ts` + `views/__tests__/CustomersView.spec.ts`:
       `type`, `company_id`, `ico`, `dic`, `address_street`,
       `address_city`, `address_zip`, `address_country`, `website`.
     - Snižuje ~12 errorů. Vitest: 36/36 passed pro upravené specs.
   - ✅ **`String#split('T')[0]` → `?? ''`** *(2026-04-30 pátá iterace)* —
     pod `noUncheckedIndexedAccess` vrací `string | undefined`. Cílilo
     na `Task.due_date`/`due_date_end` nullable mismatch + příbuzné:
     - `TaskDetailView.vue` (4 řádky: editDueDate, editDueDateEnd,
       logFormDate, recurrenceEndsAt).
     - `TasksView.vue` (editDueDate), `TaskTableView.vue` (editValue).
     - `GanttView.vue` (start/end z `_start.toISOString().split('T')[0]`
       předávané do `emit('taskDateChange', task.id, start, end)`).
     - `CalendarView.vue` (`USER_COLORS[i % USER_COLORS.length]` →
       `?? '#6b7280'` default barva).
     - Snižuje 8 errorů.
   - ✅ **`ManagementDetailView.vue` narrowing** *(2026-04-30 pátá iterace)* —
     `record.type` uvnitř `MANAGEMENT_TYPES.find(t => t.value === record.type)`
     callback ztrácí narrowing z `<template v-else>`. Použito `record?.type`
     pouze uvnitř callback (vnější `?? record.type` zůstává narrowing-OK).
     Snižuje 1 error.
   - ✅ **Sort/filter callback narrowing + EntitySidebarActionPicker
     v-model + AutomationsView nullable indexing** *(2026-04-30 šestá iterace)* —
     - `RealizationsView.vue` & `ManagementView.vue`: bucketing
       `if (map[r.status]) map[r.status].push(r); else map['planned'].push(r)`
       refaktorováno na `const bucket = map[r.status] ?? map['default']; bucket?.push(r)`
       — `noUncheckedIndexedAccess` jinak hlásil `Object is possibly 'undefined'`
       pro každé `map[key]`. Snižuje 4 errory.
     - `EntitySidebarActionPicker.vue`: `sidebarExtraFields` typ změněn z
       `Record<string, unknown>` na `Record<string, string | number | string[] | null>`,
       aby `<textarea v-model>` přijal value-type. Hodnoty jsou inicializovány
       prázdným stringem a všechny binding pole jsou textbox/select/number.
       Snižuje 1 error.
     - `AutomationsView.vue`:
       - `setActionTagsFromString`: extrahováno `const action = ruleFormActions.value[i]; if (!action) return`,
         poté přiřazení `action.tags`. Snižuje 1 error.
       - `lastRunLabel`: zavedeno `const first = runs[0]; if (!first) return ''`
         před voláním `formatDate(first.triggered_at)`. Snižuje 1 error.
   - ✅ **Dokončen `vue-tsc` cleanup — 0 errorů** *(2026-04-30 sedmá iterace)* —
     vyřešeny zbývající errory v `ActivityTimeline.vue` (5) a `AutomationsView.vue` (4).
     Vue-tsc baseline tím skončil čistý.
     - `ActivityTimeline.vue:203` (filterOptions): `_filterLabelKey[tool.activity_type]`
       je `string | undefined`; TS neprovede narrowing přes opakovaný indexed access
       v ternárním výrazu. Refaktorováno z inline ternáru na blok s lokální
       `const labelKey = _filterLabelKey[tool.activity_type]` a
       `labelKey ? t(labelKey) : tool.label`. Snižuje 1 error.
     - `ActivityTimeline.vue:422` (`userInitials`): pod `noUncheckedIndexedAccess`
       `parts[0]` a `parts[parts.length - 1]` jsou `string | undefined`, navíc
       `[0]` indexace nad nimi. Rozdělil na `const first = parts[0] ?? ''`
       / `const last = parts[parts.length - 1] ?? ''` + `(first[0] ?? '') + (last[0] ?? '')`
       s fallbackem na `'?'` když by zbylo prázdno. Snižuje 4 errory.
     - `ActivityTimeline.vue:753–754`: `(act.metadata as Record<string,string>).old_status`
       / `.new_status` jsou `string | undefined`, ale `translateLeadStatus(status: string)`
       vyžaduje `string`. Doplněn `?? ''` na obou call sites — funkce má interní
       `map[status] ?? status` fallback, takže prázdný string projde bezpečně.
       Snižuje 2 errory (= 5 v `ActivityTimeline.vue` celkem dohromady s předchozími).
     - `AutomationsView.vue:663`: literální placeholdery `{{lead_title}}`,
       `{{task_title}}`, `{{customer_name}}`, `{{due_date}}` v textovém popisku
       (instrukce pro uživatele, jaké placeholdery smí dát do
       `title_template`) Vue compiler interpretoval jako mustache výrazy a hledal
       odpovídající property na komponentě. Přidán **`v-pre`** na `<p>` element
       — celý jeho obsah se nepokouší kompilovat jako šablona, takže `{{…}}`
       zůstanou literálním textem (přesně to, co tam patří jako dokumentace).
       Snižuje 4 errory.
     - **Validace:** `npm run type-check` prochází se 0 errorů (z 13 unikátních).
       Vitest baseline beze změny: 66 failed / 102 passed (preexisting i18n setup
       issues v Team/Settings/Customers/Leads/Dashboard testech, nesouvisí
       s těmito úpravami).
4. **`Task.realization` FK + Tasks tab v Realization detail** —
   v `RealizationDetailView` je placeholder `tasks` tab; backend
   `Task` model FK na `Realization` nemá. Vyžadovalo by migrace
   + `list_tasks` filtr + i18n + UI.
5. **Sekce 5.3 / 5.4 / 5.5** v `streamline_goals.md` — analytics nad
   timeline (response time, channel mix, funnel attribution),
   automatizace (rules over Activity), integrace (e-mail/voicemail
   import). Produktové rozhodnutí, žádný blokátor.

### Čím pokračovat příští session *(stav po 2026-04-30 čtrnácté iteraci)*

Vue-tsc baseline je **kompletně čistý**, vitest baseline je **kompletně
čistý** (0 fails, 90/90 pass), oxlint čistý nad dotčeným souborem,
E2E timeline pokrývá `lead` + `task`. **První quick-win z triage
(QW-3 — multi-select filter chips) je nasazen** v
`frontend-spa/src/components/ActivityTimeline.vue`.

#### ✅ Co bylo v této session (čtrnáctá iterace, 2026-04-30) uděláno

Z plánu pro tuto session vybrán **QW-3** jako první quick-win k
implementaci — pure-FE, žádná datová migrace, nejnižší riziko, nejlepší
UX dopad. Konkrétně v `ActivityTimeline.vue`:

1. **`filterType: ref<string>('')` → `activeFilters: ref<Set<string>>(new Set())`** —
   filter je teď multi-select. Empty set = „Vše" (zobrazit všechno).
   Logika `filteredActivities` v computed: prázdná množina → vše;
   jinak `activity.type ∈ activeFilters` nebo (pokud je v setu
   synthetic „task" chip) `activity.type ∈ ['task', 'task_assigned',
   'task_completed']`. Synthetic task-group expansion zachován z
   původní implementace.
2. **`toggleFilter(value)` chip handler** — kliknutí na chip s prázdným
   value (= „Vše") vyresetuje set; jinak toggluje členství. Drží to
   zpětnou kompatibilitu s existujícím E2E (`Test 2 — filter the feed`
   v `lead-timeline.spec.ts` a `task-timeline.spec.ts` klikne na
   `comment` chip a očekává jen comment items, pak klikne na `""` All
   chip pro reset — oba kroky fungují i s novou logikou).
3. **`isFilterActive(value)` helper** — pro chip CSS class binding;
   `value === ''` je aktivní pokud je set prázdný, jinak `set.has(value)`.
   V templatu nahrazeno `:class="filterType === f.value ? ... : ..."`.
   Přidán `data-filter-active="true|false"` atribut pro přesnější
   E2E asserce v budoucnu (multi-select chips testy).
4. **Persistence do `localStorage`** — `watch(activeFilters, ...)` s
   klíčem `lead-lab.timeline.filter.{entityType}` (per-entityType, takže
   lead a task drží svoje filtry odděleně). Hydratace na mount z
   `localStorage.getItem(...)`, ignorování parse/storage chyb (best-effort,
   nesmí rozbít timeline). Empty set = `localStorage.removeItem`,
   ne `setItem('[]')` — neblokuje se quota zbytečně.
5. **Empty state hláška** — `filterType ? 'noActivitiesForFilter' : 'noActivities'`
   nahrazeno `activeFilters.size > 0 ? ... : ...`. i18n klíče beze
   změny — žádná nová překladová práce.
6. **Vue import aktualizován** — `import { ref, computed, watch, ... }
   from 'vue'` (přidáno `watch`).

**Validace:**

- `npm run type-check` — exit 0 (vue-tsc bez errorů).
- `npm run test:unit -- --run` — `Test Files 12 passed (12)`,
  `Tests 90 passed (90)`. Žádný regress.
- `oxlint src/components/ActivityTimeline.vue` — 0 warnings, 0 errors.
- E2E spec `lead-timeline.spec.ts` Test 2 + `task-timeline.spec.ts`
  Test 2 zůstávají platné: `click('[data-filter-value="comment"]')`
  → assert všechny `data-activity-type="comment"` → `click('[data-filter-value=""]')`
  → reset. Logika nové implementace (toggleFilter('') = clear) přesně
  drží tohle chování. (Nespouštím v sandboxu — vyžaduje dev server.)

**Co se NE-dělalo:**

- **UI bucketing chips** (skupiny *Komunikace* / *Změny* / *Soubory* /
  *Systém*) — sketch v sekci 5.0 to navrhuje, ale 1) zvyšuje to PR
  scope, 2) UX bucketing je samostatné rozhodnutí (závisí na tom, kolik
  toolů reálně bude v registry — dnes ~12, bucket dává smysl od ~20+).
  Necháno na follow-up PR.
- **Multi-select E2E test** — existující single-select E2E pokrývá
  hot-path; nový test by jen testoval, že po kliknutí na *dva* chips
  (např. `comment` + `email_out`) je v DOM jen ten průnik typů, plus
  reload-persist ověření přes `localStorage`. Přidá se až s entity
  E2E specs (customer/realization/management/proposal), kde dává
  smysl bundlovat.

#### Co dál

1. **Multi-select E2E** — přidat 5. test do `lead-timeline.spec.ts`
   (a podobný do `task-timeline.spec.ts`):
   ```ts
   test('multi-select filter persists across reload', async ({ page }) => {
     // … seed druhý activity typ (např. status_change přes API)
     await page.locator('[data-filter-value="comment"]').click()
     await page.locator('[data-filter-value="status_change"]').click()
     // assert: pouze items s typem comment / status_change viditelné
     await page.reload()
     // assert: chips comment + status_change stále data-filter-active="true",
     // feed stále filtrovaný
   })
   ```
2. **Dokončit E2E timeline coverage pro zbylé 4 entity** — stále
   prioritní (12. iterace) — `customer-timeline.spec.ts`,
   `realization-timeline.spec.ts`, `management-timeline.spec.ts`,
   `proposal-timeline.spec.ts` + sdílený `_fixtures.ts`. Multi-select
   test bude součástí šablony.
3. **Další quick-win z triage** — po dokončení E2E suite vzít buď
   **QW-1** (`Activity.is_internal` boolean — jednoduchá migrace +
   serializer flag), nebo **QW-5** (`gettext_lazy` na Streamline labels —
   čistě mechanická). Oba bez závislostí.
4. **QW-2 (`Activity.is_pinned`)** — sketch v sekci 5.0 je hotový;
   PR vyžaduje migraci + úpravu `PinnedTool` / `UnpinnedTool` v
   `crm/streamline/tools.py` + filter parametr na `ActivityViewSet` +
   sticky pinned section v `ActivityTimeline.vue`. Větší než ostatní
   quick-wins, ale stále vejde do 1 PR.
5. **`Task.realization` FK** — neudělané, mimo scope timeline.

#### ✅ Co bylo v třinácté iteraci (2026-04-30) uděláno

Práce čistě nad dokumentem `streamline_goals.md`, sekce 5 *Future
improvements*. Sekce předtím obsahovala ~30 plochých nápadů přes 7
oblastí (5.1–5.7), bez priority a bez závislostí — typický parking lot.
Aby z toho šlo začít přírůstkově dělat PR, přidána triage vrstva
**5.0 Triage — quick-wins, foundations, strategic**:

1. **Tabulka 🟢 Quick-wins (6 položek, 1 PR každá)** — `Activity.is_internal`
   boolean, `Activity.is_pinned` triplet (boolean + `pinned_at` +
   `pinned_by`), filter chip po `activity_type` v timeline (pure-FE),
   `select_related` / `prefetch_related` audit, `gettext_lazy` na
   `StreamlineTool.label` / `icon`, GDPR export endpoint per Customer.
   Žádná z nich neblokuje další → dají se rozdat napříč týmem paralelně.
2. **Tabulka 🟡 Foundations (6 položek)** — `parent_activity` self-FK,
   soft delete (`deleted_at`), `validate_payload` přes `jsonschema`,
   deklarativní `permissions` scope, retention policy, inbound webhook
   router. Tyto odemykají další features (threading UI, retention,
   integrace) a mají závislosti, takže se musí dělat sériově ve Sprintu B.
3. **Sekce 🔴 Strategic** — 8 položek, které by měly samostatný design
   doc (polymorfní FK, partitioning, async Celery, undo, AI insights,
   calendar/e-sign sync, Redis cache, field-level encryption).
   Argument *proč zatím ne* u každé.
4. **Doporučená sekvence** — Sprint A (paralelní quick-wins),
   Sprint B (sériově F-3 → F-4 → F-1 → F-2 → F-5), Sprint C (F-6 po F-3).
5. **Quick-win sketche pro QW-2 a QW-3** (vybrané jako největší UX dopad
   za nejmenší úsilí) — konkrétní migrace + endpoint + UI plán u
   `is_pinned` a filter-chips. Ostatní quick-wins jsou dost přímočaré,
   aby stačila tabulka.

Sekce 5 zůstává parking-lot pro nápady, jen má teď strukturu, aby šlo
říct „příští sprint vezmeme QW-1 + QW-2 + QW-3" místo „někdy bychom
měli vylepšit timeline".

#### ✅ Co bylo v dvanácté iteraci (2026-04-30) uděláno

Pokračování plánu z 11. iterace — replikace timeline E2E specu z
`lead` na `task` entitu. Klíčový rozdíl: `TaskDetailView.vue` nepoužívá
`EntitySidebarActionPicker` (sidebar Quick Actions), ale rovnou
**in-component composer** přímo v `ActivityTimeline` (composer není
schovaný — `:hide-composer="true"` se na Task NEpředává). Selektory
jsou tudíž jiné než u leadu:

| Lead (sidebar)                          | Task (in-component)              |
| --------------------------------------- | -------------------------------- |
| `entity-sidebar-action-option`          | `activity-action-option`         |
| `entity-sidebar-action-submit`          | `activity-composer-submit`       |
| `entity-sidebar-action-picker` (root)   | `activity-timeline-composer`     |

1. **Verifikace UI patternu** — `grep` v `TaskDetailView.vue` potvrdil,
   že `<ActivityTimeline ref entity-type="task" :entity-id="taskId" />`
   se vykresluje **bez** `:hide-composer`, takže in-component composer
   z `ActivityTimeline.vue` (řádky 574-693, dva submit buttony:
   `activity-composer-submit` pro comment/call/meeting/email, a
   `activity-composer-task-submit` pro vnořený task — pro náš spec
   zajímavý ten první). Grep selektorů v `ActivityTimeline.vue` ukázal
   všechny `data-testid` přidané v 10. iteraci jsou dostupné i v
   in-component composer větvi.
2. **Nový soubor `e2e/tests/task-timeline.spec.ts`** (130 řádků, 4 testy
   v `test.describe.serial`, sdílený `taskId`, struktura 1:1 jako
   `lead-timeline.spec.ts`):
   - **`beforeAll`** — `POST /api/v1/crm/tasks` s `{ title }` (z
     `TaskIn` schema je `title` jediný required field, vše ostatní má
     default).
   - **Test 1 — Add comment:** `[data-testid="activity-action-option"]
     [data-action="comment"]` → fill Tiptap → `activity-composer-submit`.
   - **Testy 2-4** — filter chip / reaction toggle / persist přes
     reload: identické se `lead-timeline.spec.ts` (timeline feed +
     reaction selektory jsou společné pro obě entity, jelikož pochází
     ze stejné `ActivityTimeline.vue` komponenty).
3. **Validace:** `./node_modules/.bin/playwright test --list
   tests/task-timeline.spec.ts` listuje všechny 4 testy v
   `chromium` + `mobile-chrome` projektech. TypeScript + Playwright
   API parsing OK. (Pozn.: lokální `./node_modules/.bin/playwright`
   je nutné použít místo `npx`, který v sandboxu sahá do globální
   cache se starší verzí Playwrightu, jež neumí načíst aktuální
   `playwright.config.ts`.)

**Stav E2E suite po této session:**

| Entity        | Spec file                                | Composer typ        |
| ------------- | ---------------------------------------- | ------------------- |
| lead          | `e2e/tests/lead-timeline.spec.ts` ✅      | sidebar picker      |
| task          | `e2e/tests/task-timeline.spec.ts` ✅      | in-component        |
| customer      | (chybí)                                  | TBD                 |
| realization   | (chybí)                                  | TBD                 |
| management    | (chybí)                                  | TBD                 |
| proposal      | (chybí)                                  | sidebar picker      |

#### Co dál

1. **Zjistit composer typ pro customer / realization / management** —
   stačí `grep "ActivityTimeline" frontend-spa/src/views/{Customer,Realization,Management}DetailView.vue`
   a podívat se, jestli má `:hide-composer="true"` a paralelní
   `<EntitySidebarActionPicker>` (jako lead) nebo composer in-component
   (jako task). Podle toho zvolit selektor pattern z tabulky výše.
2. **Replikovat spec pro zbylé 4 entity** — `customer-timeline.spec.ts`,
   `realization-timeline.spec.ts`, `management-timeline.spec.ts`,
   `proposal-timeline.spec.ts`. Šablona je již ustálena (lead pro
   sidebar variantu, task pro in-component variantu). Seed přes
   API endpoints `POST /api/v1/crm/{customers,realizations,managements,proposals}`
   — ověřit u každé, jaké je minimální required payload (např.
   customer asi vyžaduje `name`, proposal pravděpodobně `lead_id`
   nebo `title`).
3. **Sdílený helper** — po 3. duplicitním specu už dává smysl:
   extrahovat do `e2e/tests/_fixtures.ts` factory typu
   ```ts
   export async function seedEntity(request, kind, payload) { ... }
   export async function addCommentViaComposer(page, composerType, text) { ... }
   ```
   a v každém spec souboru jen volat. Sníží to riziko drift mezi
   specy a usnadní budoucí změny v UI (např. když se sidebar/in-comp
   pattern sjednotí).
4. **CI workflow** — po dopsání všech 6 specs přidat
   `.github/workflows/e2e.yml` job: spustit backend + frontend přes
   `docker-compose`, počkat na health, pak `cd e2e && npm test`.
   Mimo scope, dokud spec sada není kompletní.
5. **`Task.realization` FK + Tasks tab v Realization detail** —
   placeholder tab v `RealizationDetailView` čeká na backend FK.
   Mimo scope timeline E2E, ale stále na seznamu.
6. **Sekce 5.3 / 5.4 / 5.5** — analytics / automatizace / integrace
   nad timeline. Produktové rozhodnutí, žádný blokátor.

### Předchozí sessions *(2026-04-30 první až jedenáctá iterace)*

#### ✅ Co bylo v jedenácté iteraci (2026-04-30) uděláno

Napsání prvního E2E specu pro timeline UX — přímý follow-up na 10.
iteraci, kde byly přidány `data-testid` atributy. Tím se zavřel
plánovaný „Krok 1 — E2E testy timeline UX" pro `lead` entitu.

1. **Nový soubor `e2e/tests/lead-timeline.spec.ts`** (130 řádků, 4 testy
   v `test.describe.serial`, sdílí jeden `leadId` napříč testy):
   - **`beforeAll`** — vytvoří lead přes `POST /api/v1/crm/leads` (rychlejší
     než New Lead modal, méně závislé na UI textech). Title obsahuje
     `Date.now()` pro uniqueness mezi běhy.
   - **Test 1 — Add comment via sidebar:** klikne na
     `[data-testid="entity-sidebar-action-option"][data-action="comment"]`,
     vyplní Tiptap RichTextEditor (`[contenteditable="true"]`), klikne
     `entity-sidebar-action-submit`, ověří že nová `activity-item`
     s `data-activity-type="comment"` obsahuje text.
   - **Test 2 — Filter feed:** klikne filter chip
     `[data-testid="activity-timeline-filter"][data-filter-value="comment"]`,
     prochází všechny viditelné `activity-item` a asserts, že každý má
     `data-activity-type="comment"`. Reset na all-filter na konci.
   - **Test 3 — Reaction toggle:** otevře `activity-add-reaction` na
     komentu, vybere `[data-emoji="👍"]` z `activity-emoji-picker`,
     ověří že `activity-reaction-chip[data-emoji="👍"]` obsahuje text
     `1`. Druhý klik na chip → `toHaveCount(0)` (chip zmizí).
   - **Test 4 — Persist přes reload:** `await page.reload()` →
     komentář je stále viditelný (timeline se znovu načítá z API).
2. **Validace:** `npx playwright test --list tests/lead-timeline.spec.ts`
   listuje všechny 4 testy v obou Playwright projektech (`chromium`,
   `mobile-chrome`) — TypeScript syntaxe + Playwright API parsing OK.
   Vlastní běh testu vyžaduje běžící backend + frontend dev server,
   což je v sandboxu mimo scope (CI Playwright workflow toto pokryje).
3. **Konzistence s `lead-lifecycle.spec.ts`:** stejný pattern
   `test.describe.serial` + sdílený seed lead, jen výrazně robustnější
   selektory díky `data-testid` (locator-only, ne `getByRole` /
   `getByText` které jsou citlivé na i18n).

**Pozn. ke `Test 3` (reaction):** `activity-add-reaction` button je
viditelný permanentně (ne na hover) v current designu, takže není třeba
hover triggera. Pokud by se design změnil na hover-only, stačí
předtím doplnit `await commentItem.hover()`.

#### Co dál

1. **Replikovat E2E pro task** — `e2e/tests/task-timeline.spec.ts` —
   stejné 4 testy nad `/app/tasks/{id}`. Task má specifikum: jeho
   `LeadDetailView`-style stránka také používá `EntitySidebarActionPicker`
   nebo `ActivityTimeline` composer? Zkontrolovat
   `frontend-spa/src/views/TaskDetailView.vue` (z 9. iterace
   `streamline_goals.md` známo, že legacy timeline byla nahrazena
   `<ActivityTimeline ref entity-type="task" :entity-id="taskId" />` —
   ale nevím, jestli je composer skrytý a používá se sidebar picker,
   nebo composer in-component). Podle toho upravit selektory v
   prvním testu (in-component composer používá
   `activity-action-option` + `activity-composer-submit`).
2. **Replikovat E2E pro customer / realization / management / proposal** —
   stejný šablona, poslední 4 entity. `proposal` má specifický
   builder UI (z 8. iterace) — composer je v Builder dolní sekci,
   ale stále jako `EntitySidebarActionPicker`. Tedy selektory jsou
   přenositelné 1:1.
3. **Sdílený helper** *(nice-to-have)* — pokud se ukáže, že kód
   `seedLead/seedTask/seedCustomer/...` se opakuje, extrahovat do
   `e2e/tests/_fixtures.ts` (`createLead(request, title)` →
   `Promise<string>`). Zatím ne potřeba (jen 1 entita pokrytá).
4. **CI workflow** — po dopsání všech 6 specs se může v `.github/workflows/`
   přidat E2E job, který spustí backend + frontend přes
   `docker-compose` a pak `playwright test`. Ale to je až po doplnění
   všech specs (zbytečné spouštět neúplnou sadu).
5. **`Task.realization` FK + Tasks tab v Realization detail** —
   placeholder tab v `RealizationDetailView` čeká na backend FK.
   Vyžaduje migraci + `list_tasks` filtr + i18n + UI. Mimo scope
   timeline E2E, ale na seznam si to zaslouží zůstat.
6. **Sekce 5.3 / 5.4 / 5.5** — analytics / automatizace / integrace
   nad timeline. Produktové rozhodnutí, žádný blokátor.

### Předchozí sessions *(2026-04-30 první až desátá iterace)*

#### ✅ Co bylo v desáté iteraci (2026-04-30) uděláno

Doplnění `data-testid` atributů do timeline komponent — prerekvizita
plánovaného „Krok 1 — E2E testy timeline UX" z minulé session.
Bez `data-testid` by Playwright selektory musely spoléhat na
i18n textové popisky (křehké vůči přepnutí jazyka) nebo class names
(křehké vůči Tailwind redesignu).

1. **`ActivityTimeline.vue`** — přidáno celkem **13 `data-testid`
   atributů**, pokrývající všechny interaktivní cesty timeline:
   - **Root + sekce:** `activity-timeline` (root), `activity-timeline-composer`,
     `activity-timeline-loading`, `activity-timeline-empty`,
     `activity-timeline-list`, `activity-timeline-load-more`.
   - **Composer (in-component):** `activity-action-option` (s
     `data-action="<activity_type>"` pro výběr typu), submit tlačítka
     `activity-composer-submit` a `activity-composer-task-submit`.
   - **Filter chips:** `activity-timeline-filter` s `data-filter-value`
     (== `''` pro "all", nebo konkrétní `activity_type`).
   - **Activity items:** `activity-item` s `data-activity-id` +
     `data-activity-type` na každém řádku — selektor `[data-testid="activity-item"][data-activity-type="email_out"]`
     je triviální i ve vícejazyčném prostředí.
   - **Reactions:** `activity-reactions-row` (kontejner),
     `activity-reaction-chip` s `data-emoji` (existující agregovaná
     reakce, kliknutí toggle), `activity-add-reaction` (`+` button
     otevírající picker), `activity-emoji-picker` (popover),
     `activity-emoji-option` s `data-emoji` (volba emoji).
2. **`EntitySidebarActionPicker.vue`** — přidány **4 `data-testid`**:
   - Root: `entity-sidebar-action-picker`.
   - Action options: `entity-sidebar-action-option` s
     `data-action="<activity_type>"`.
   - Submit: `entity-sidebar-action-submit` (activity form),
     `entity-sidebar-task-submit` (task quick-create).
3. **Validace:**
   - `npm run type-check` — **0 errorů** (baseline zachovaný).
   - `npx vitest run` — 12/12 file pass, 90/90 test pass (baseline
     zachovaný; 35 pre-existing unhandled rejections v Settings/Customers
     specs nezávisle na této změně).
   - Žádná funkční ani styling změna (atributy jsou pouze metadata pro
     testy, neovlivňují DOM rendering ani CSS).

**Konvence pojmenování** *(pro budoucí komponenty + testy):*
- `<komponenta>` namespace prefix (`activity-`, `entity-sidebar-`).
- Pro opakovatelné prvky doplnit `data-<discriminator>` (např.
  `data-activity-type`, `data-emoji`, `data-action`) — Playwright pak
  může napsat `page.locator('[data-testid="activity-item"][data-activity-type="comment"]').first()`
  bez závislosti na pořadí v DOM.

#### Co dál

1. **Napsat `lead-timeline.spec.ts`** — teď, když máme `data-testid`,
   může vzniknout E2E spec pokrývající:
   - `await page.goto('/app/leads/{id}')` na lead z fixture
   - `[data-testid="entity-sidebar-action-option"][data-action="comment"]`
     → klik → fill RichTextEditor → `[data-testid="entity-sidebar-action-submit"]` → klik
   - assert `[data-testid="activity-item"][data-activity-type="comment"]` první v listu
   - filter chip `[data-testid="activity-timeline-filter"][data-filter-value="email_out"]` →
     ověřit, že žádné `comment` items nejsou viditelné
   - reaction toggle: hover na první comment → klik
     `[data-testid="activity-add-reaction"]` → klik
     `[data-testid="activity-emoji-option"][data-emoji="👍"]` → ověřit
     `[data-testid="activity-reaction-chip"][data-emoji="👍"]` text obsahuje "1" →
     druhý klik → chip zmizí.
   - Persist přes reload: `await page.reload()` → comment + reaction zůstanou.
   Tyto testy patří do `e2e/tests/lead-timeline.spec.ts` (nový soubor),
   nebudou kolidovat s existujícím `lead-lifecycle.spec.ts`.
2. **Replikovat E2E pro ostatní entity** — po lead spec napsat zkrácenou
   variantu pro `task` (`/app/tasks/{id}`), `customer`, `realization`,
   `management`, `proposal`. Stejný `data-testid` selektor model funguje
   napříč entitami díky generickému `ActivityTimeline` + `EntitySidebarActionPicker`.
3. **`Task.realization` FK + Tasks tab v Realization detail** —
   placeholder tab v `RealizationDetailView` čeká na backend FK.
   Vyžaduje migraci + `list_tasks` filtr + i18n + UI.
4. **Sekce 5.3 / 5.4 / 5.5** — analytics / automatizace / integrace
   nad timeline. Produktové rozhodnutí, žádný blokátor.

### Předchozí sessions *(2026-04-30 první až devátá iterace)*

#### ✅ Co bylo v deváté iteraci (2026-04-30) uděláno

Úklid omylem committnutých `vue-tsc` / `tsc` emit artefaktů z
`frontend-spa/src/` — celkem **75 souborů smazáno**:

1. **Identifikace** — `git ls-files 'frontend-spa/src/**/*.js'` vrátilo
   75 souborů (74 pod `src/`, plus `postcss.config.js` v rootu, který je
   legitimní config a zůstává). Každý `.js` měl `.ts` nebo `.vue`
   sourcing sibling (např. `Button.vue` + `Button.vue.js`,
   `main.ts` + `main.js`, `auth.spec.ts` + `auth.spec.js`).
   Hlavičky souborů (`/// <reference types=".../@vue/language-core/..."`)
   potvrdily, že jde o emit z `vue-tsc`, ne ručně psaný kód.
2. **Kontrola, že žádný runtime import je nepoužívá** — `index.html`
   ukazuje na `/src/main.ts`, vite alias chain je celá TS, vitest
   `include` filtr (přidaný v 8. iteraci) artefakty ignoroval.
   Žádná regrese hrozit nemůže.
3. **`git rm`** všech 75 souborů jedním batch příkazem.
4. **`frontend-spa/.gitignore`** rozšířen o patterny pro
   tsc/vue-tsc emit pod `src/`:
   - `src/**/*.vue.js`, `src/**/*.spec.js`, `src/**/*.stories.js`
   - `src/main.js`, `src/App.vue.js`, `src/design-tokens.js`
   - `src/{components,views,stores,plugins,composables,api,router,utils,types,locales,test}/**/*.js`
   - To zajistí, že případný omylem spuštěný `tsc --emit` nebo
     `vue-tsc` bez `--noEmit` už víc nenacommituje stejné soubory.
5. **Validace:** `npm run type-check` prochází se 0 errory; `vitest run`
   12/12 file pass, 90/90 test pass — beze změny proti baseline.
   Code review není potřeba (čistě delete + .gitignore).

**Výsledek:** repo je o 75 mrtvých souborů menší, vue-tsc baseline
zůstává čistý, vitest baseline zůstává čistý.

#### Co dál

1. **E2E testy timeline UX** *(sekce 4.10 — Fáze 5 follow-up)* — pro
   každou entitní timeline (lead, task, realization, management, customer,
   proposal) ověřit happy-path s Playwrightem (`e2e/tests/`). Zatím
   pokryté pouze backend unit testy v `crm/tests.py` + frontend unit
   smokes. **Doporučený další krok** — má jasný scope, přímo navazuje na
   uzavřenou Fázi 5 a zvedne konfidenci nasazení. Začít doporučuju s
   `lead` (nejjednodušší entita, kompletní pokrytí
   `EntitySidebarActionPicker` + reactions + filter), pak postupně
   `task` → `customer` → `realization` → `management` → `proposal`.
   Existující `e2e/tests/lead-lifecycle.spec.ts` už pokrývá comment +
   task happy-path; nový `lead-timeline.spec.ts` by měl ověřit:
   - načítání feedu po reload (persist přes ActivityWS)
   - `EntitySidebarActionPicker` — open → vybrat tool → submit → ověřit
     novou aktivitu v timeline
   - filter chip — kliknout `email` → vidět jen email-typed aktivity
   - reaction toggle — kliknout 👍 → chip s count `1` se objeví,
     druhý klik → zmizí
   Před psaním E2E pravděpodobně přidat `data-testid` atributy do
   `ActivityTimeline.vue` a `EntitySidebarActionPicker.vue` (dnes žádné
   nemají, role/text selektory jsou křehké vůči i18n a class-only
   elementům).
2. ~~**Vyčistit committed `.js` build artefakty**~~ — ✅ hotovo v této
   (deváté) session, viz výše.
3. **`Task.realization` FK + Tasks tab v Realization detail** —
   placeholder tab v `RealizationDetailView` čeká na backend FK.
   Vyžaduje migraci + `list_tasks` filtr + i18n + UI.
4. **Sekce 5.3 / 5.4 / 5.5** — analytics / automatizace / integrace
   nad timeline. Produktové rozhodnutí, žádný blokátor.

### C) Pokračovat s úklidem Fáze 2 + 3 backend *(už hotovo — viz výše)*

Když odpadla povinnost migrovat data, dříve odložené úklidové fáze jsou
triviální:

- **Fáze 2 (`LeadStatusHistory`)**: smazat model + zápis ze
  `StatusChangeTool.process_action`. Reporty velocity přepsat nad
  `Activity.objects.filter(type="status_change")`. `RunSQL DROP TABLE`
  bez `RunPython`.
- **Fáze 3 (`LeadAttachment` / `TaskAttachment`)**: smazat modely +
  endpointy + frontendové komponenty. `Document` pokrývá vše. Migrační
  `migrations.DeleteModel`, žádný převod souborů (dev data se zahodí).

### D) Co opravdu necháme stranou *(nezměněno)*

- Threading přes `parent_activity` FK
- Pinned section, saved views, drafts, slash commands
- Inbound webhook router, calendar 2-way sync, e-sign provider plugin
- Soft delete + edit history
- Performance audit (materialized view, partitioning)

Tyto body jsou v sekci 5 níže — pořád future work, jen už ne blokátor pro
uzavření Fáze 4 + 5.

---

## 4. Rizika a na co dát pozor

> **Aktualizace 2026-04-29:** body zmiňující datovou migraci, deprecation
> cycle a zpětnou kompatibilitu jsou pro nás bezpředmětné — aplikace je
> pořád v ranné dev fázi, žádná produkční data ani externí klienti zatím
> nejsou.

- ~~**Migrace dat je nevratná**~~ — *neaplikuje se*; modely lze smazat
  rovnou bez `RunPython` převodu, dev DB se v případě potřeby recreatuje.
- **`TaskTimelineEntry.parent_entry` (threading)** — v `Activity` dnes není ekvivalent. Buď přidat
  `parent_activity` FK (jednoduché), nebo vědomě threading zrušit; doporučuji přidat FK.
- **`Activity` má `firm` jen přes entitu** — Task má `firm` napřímo, takže to je OK, ale ujisti se,
  že WebSocket broadcasting na firm-channel funguje stejně.
- **`StatusChangeTool` dnes v `process_action` přepisuje `lead.status`** — když smažeme
  `LeadStatusHistory`, samotná logika status změny zůstává, jen vypadne ten druhý zápis.
  Bez problémů.
- ~~**API zpětná kompatibilita**~~ — *neaplikuje se*; SPA je jediný
  konzument, endpointy lze odstranit synchronně s frontendem v jednom PR.
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

---

## 5. Future improvements *(parking lot — návrhy nad rámec současných 6 fází)*

> Nápady pro další iterace, jakmile bude Phase 0–6 v provozu. Žádný z nich není naléhavý,
> ale stojí za to je mít sepsané, ať na ně můžeme v budoucnu mrknout.

### 5.0 Triage — quick-wins, foundations, strategic

Sekce 5 dnes obsahuje ~30 nápadů přes 7 oblastí. Aby šlo začít přírůstkově, dělím
je do tří košíků podle poměru přínos / risk / úsilí. **Quick-wins** jsou věci do
1 PR bez datové migrace nebo s triviální migrací; **foundations** odemykají další
features (typicky 1–3 PR + migrace); **strategic** jsou velké projekty na
samostatný design doc.

#### 🟢 Quick-wins *(1 PR, bez breaking změn, samostatně nasaditelné)*

| # | Položka | Oblast | Proč teď |
| --- | --- | --- | --- |
| QW-1 | `Activity.is_internal` boolean | 5.1 | 1× sloupec + serializer flag; odemyká „interní poznámka" v UI bez migrace dat. |
| QW-2 | `Activity.is_pinned` + `pinned_at` + `pinned_by` | 5.1 | 3× sloupce; existující `PinnedTool` / `UnpinnedTool` pak jen toggluje boolean. Dnes je dotaz „pinnuté pro lead" drahý (musí se procházet eventy). |
| QW-3 | Filter chip po `activity_type` v timeline | 5.3 | Pure-FE; data už máme (`data-activity-type` v DOM). Multi-select chip nad feedem, persist do `localStorage`. |
| QW-4 | `select_related` / `prefetch_related` audit | 5.6 | Django Debug Toolbar/silk profiling nad `ActivityOut` serializací; jeden PR s opravami N+1 v `user`, `tool_payload`, `reactions`. |
| QW-5 | `gettext_lazy` na `StreamlineTool.label` / `icon` | 5.2 | Mechanická změna v `crm/streamline/tools.py`; cs/en/sk catalog už projekt má. |
| QW-6 | GDPR export endpoint per Customer | 5.7 | Read-only endpoint `GET /api/v1/crm/customers/{id}/gdpr-export` → ZIP z `Activity.objects.filter(customer=...)` + `Document` blobs. Žádná schémová změna. |

Dohromady 6 PR, žádný neblokuje další; dají se rozdat napříč týmem paralelně.

#### 🟡 Foundations *(odemykají UX/strategic items, typicky 1–3 PR + migrace)*

| # | Položka | Oblast | Co odemyká |
| --- | --- | --- | --- |
| F-1 | `Activity.parent_activity` self-FK | 5.1 | 5.3 inline reply (tree-render), serverový `prefetch_related("replies")`, count „kolik odpovědí". Nahrazuje dnešní `metadata.reply_to_id` (data-migrace v jednom batchi). |
| F-2 | `Activity.deleted_at` (soft delete) | 5.1 | UI „komentář byl smazán" + audit zachová historii. Pre-req pro retention policy (F-5). |
| F-3 | `StreamlineTool.validate_payload` (JSON Schema enforce) | 5.2 | Centrální validace přes `jsonschema` před `process_action`; smazat ad-hoc `if not payload.get(...)` v jednotlivých toolech. Pre-req pro inbound webhook router (S-1). |
| F-4 | `StreamlineTool.permissions` deklarativní scope | 5.2 | Jednotná auth na `streamline/api.py`; pre-req pro public proposal view + multi-tenant role-based access. |
| F-5 | Retention policy per tool *(konfigurovatelná)* | 5.6 | `entity_change` / `system_note` po N měsících → archive table nebo agregovat. Závisí na F-2 (soft delete). |
| F-6 | Inbound webhook router `/inbound/{provider}/{kind}` | 5.5 | Sjednocuje dnešní roztříštěné Twilio/Postmark/WhatsApp handlery. Závisí na F-3 (payload validation). |

#### 🔴 Strategic *(samostatný design doc, 4+ PR, riziko / náklady)*

- **5.1 Polymorfní FK přes `entity_type` + `entity_id`** — ztráta DB integrity, řešit jen pokud reálně hrozí explose nullable FK sloupců (dnes 6, snesitelné).
- **5.1 Partitioning po `created_at` / cold-storage do BigQuery** — až bude největší firma > 5M aktivit.
- **5.2 Async `process_action` přes Celery** — vyžaduje queue infrastrukturu + dead-letter handling; pro AI/signature tooly stačí zatím sync s timeout.
- **5.2 `StreamlineTool.undo()`** — riziko nekonzistencí (např. pin/unpin OK, ale „undo SMS" pošle revoke?); zatím raději nedělat.
- **5.4 AI insights / funnel attribution / next-best-action** — vlastní ML pipeline + product discovery; mimo „infrastruktura timeline".
- **5.5 Calendar two-way sync, e-sign provider plugin, outbound provider abstraction** — každé je samostatný integrační projekt s vlastním provider lock-in rizikem.
- **5.6 Materialized view / Redis feed cache** — zbytečné, dokud nemáme změřený throughput problém.
- **5.7 Field-level encryption (`pgcrypto`)** — komplikuje migrace + reporting; ano pro PII jako `signer_email`, ne plošně.

#### Doporučená sekvence nasazení

```
Sprint A (paralelně):  QW-1, QW-2, QW-3, QW-4, QW-5, QW-6
Sprint B (sériově):    F-3 → F-4 → F-1 → F-2 → F-5
Sprint C (po F-3):     F-6  (inbound webhook router)
Strategic:             samostatný backlog, řešit ad-hoc
```

Po Sprintu A máme reálné UX zlepšení (filter, pinned, GDPR) bez datové
migrace. Sprint B drží pořadí kvůli závislostem (validation → permissions →
threading → soft delete → retention). Sprint C dává smysl, jakmile máme
F-3 pro JSON-schema enforcement na příchozí payload.

#### Quick-win sketche *(pro QW-2 a QW-3 — nejhmatatelnější UX dopad)*

**QW-2 — `Activity.is_pinned` boolean (≈ 1 PR)**

- Migrace: `Activity.is_pinned = BooleanField(default=False, db_index=True)`,
  `pinned_at = DateTimeField(null=True, blank=True)`,
  `pinned_by = ForeignKey(User, null=True, blank=True, on_delete=SET_NULL)`.
- `PinnedTool.process_action`: vedle dnešního zápisu `Activity(type="pinned")`
  také `target_activity.is_pinned = True; pinned_at = now(); pinned_by = user`.
  `UnpinnedTool` analogicky.
- API: `GET /api/v1/crm/leads/{id}/activities?is_pinned=true` (filter na `ActivityViewSet`).
  Bez UI ještě užitečné pro reporty.
- UI (5.3 pinned section): nad `ActivityTimeline` feedem sticky sekce, která
  čte `is_pinned=true` z téhož endpointu; pinned aktivity v hlavním feedu zůstávají
  (ne mizí), jen se duplikují nahoře — známý UX pattern (Slack, Linear).
- Audit trail (`pinned` / `unpinned` activity entries) zůstává — jen už není
  *primárním zdrojem* informace „je to pinnuté".

**QW-3 — Activity-type filter chips (≈ 1 PR, pure FE)**

- `ActivityTimeline.vue` už dnes posílá `data-activity-type` do DOM (potvrzeno
  z 10. iterace `data-testid` práce).
- Stav: `const activeTypes = ref<Set<string>>(new Set())`, prázdný = ukaž vše.
- Toolbar nad feedem: chips skupinované do logických bucketů
  (`Komunikace`: comment / email_in / email_out / sms_in / sms_out / whatsapp /
  call; `Změny`: status_change / assignee_change / priority_change / due_date_change;
  `Soubory`: file_upload / voice_memo; `Systém`: system_note / entity_change).
- Persist do `localStorage` pod klíčem `lead-lab.timeline.filter.{entityType}`.
- E2E: již existující `lead-timeline.spec.ts` Test 2 testuje filter chip pro
  jeden typ (`comment`); rozšířit na multi-select v rámci téže suite.
- Pozn.: tohle je pure-FE, žádný backend filter ani změna serializace —
  filtruje se klient-side nad celým feedem (timeline má i tak limit ~100 entries
  v jednom načtení; pokud pojede pagination, posunout do query paramu později).

### 5.1 Datový model `Activity`

- **Threading přes `parent_activity` FK** — místo dnešního `metadata.reply_to_id` udělat
  fyzický self-FK `Activity.parent_activity`. Umožní `prefetch_related("replies")`,
  serverový tree-render a indexované dotazy „kolik odpovědí má tato aktivita".
- **`is_pinned` / `pinned_at` / `pinned_by` přímo na `Activity`** — dnes řešíme přes
  `PinnedTool` / `UnpinnedTool`, což je hezký audit, ale dotaz „dej mi pinnuté aktivity
  pro tento lead" je drahý. Boolean na `Activity` + zachování pin/unpin logu jako
  doplňkový audit trail.
- **`is_internal` flag** — odlišit interní poznámky / komentáře, které nesmí vidět
  klient (např. v public proposal view nebo v exportu).
- **`visibility` enum** (`public` / `firm` / `team` / `private`) — granulárnější než
  `is_internal`, hodí se až systém poroste.
- **Soft delete (`deleted_at`)** — místo hard `DELETE` aktivity; uživatel uvidí
  „komentář byl smazán", historie zůstane.
- **Editace + edit history** — `edited_at`, `edit_count` + vedlejší `ActivityEdit`
  model s diffy. Dnes je `Activity` immutable.
- **Polymorfní entitní reference přes generic FK / dedikovanou pivot tabulku** — místo
  N nullable FK (`lead`, `realization`, `management`, `customer`, `proposal`, `task`)
  zvážit jednu `entity_type` + `entity_id` dvojici. Snižuje počet sloupců, ale ztrácí
  cizí klíčovou integritu — netrhat zatím, jen mít na radaru.
- **Partitioning / archivace** — pro firmy s milióny aktivit zvážit Postgres native
  partitioning po `created_at` nebo cold-storage do BigQuery / S3.

### 5.2 Streamline framework

- **`StreamlineTool.permissions`** — deklarativní permission scope per tool
  (např. `requires=["task.assign"]`), aby `streamline/api.py` mohl uniformně
  validovat oprávnění před `process_action`. Dnes to řešíme ad-hoc v jednotlivých
  toolech.
- **`StreamlineTool.validate_payload(payload)`** — JSON Schema validace pomocí
  `jsonschema` knihovny zapnutá centrálně před `process_action`. Dnes schéma jen
  popisuje SPA renderer, ale neenforceuje.
- **Webhook trigger per tool** — každá aktivita po `process_action` může volat
  registered webhook (pro Zapier / Make / vlastní backend klienta). Vázat na
  `tool.activity_type`.
- **Async `process_action` přes Celery** — některé tooly (AI summary, signature
  webhook) jsou pomalé. Podpora flagu `tool.async = True`, který pošle
  `process_action` do queue.
- **`StreamlineTool.undo()`** — reverzibilita pro idempotentní side-effecty
  (zruš notifikaci, reverzní pin). Užitečné pro „undo" v UI.
- **i18n labels / icons** — `label` a `icon` aktuálně hardkódované anglicky.
  Zavést `gettext_lazy` / per-locale slovník.

### 5.3 UX / Frontend

- **Filtr v timeline po `activity_type`** — multi-select chips: „skrýt
  `entity_change`", „jen e-maily a SMS". Dnes UI ukazuje vše.
- **Pinned section nad feedem** — sticky horní sekce s `is_pinned=True` aktivitami
  (po implementaci 5.1 `is_pinned`).
- **Saved views** — uložit kombinaci filtrů jako pojmenovaný view (např.
  „Klientská komunikace" = `email_*` + `sms_*` + `whatsapp_*` + `call`).
- **Inline reply (threading UI)** — po implementaci `parent_activity` umožnit
  odpovídat přímo pod komentářem, render jako tree.
- **Drafts** — autosave rozepsaného komentáře / e-mailu do localStorage + per-user
  draft endpoint.
- **Slash commands v komposeru** — `/task`, `/meeting`, `/link` přepne komposer
  na příslušný tool bez kliku do toolbaru.

### 5.4 Reporting / Analytics

- **Activity heatmap** — kalendářní heatmap aktivit per uživatel / per lead.
- **Response-time SLA** — time-to-first-response na inbound aktivitě (`email_in`,
  `sms_in`, `whatsapp_in`); upozornění při překročení SLA.
- **Channel mix dashboard** — kolik komunikace teče přes který kanál
  (e-mail vs. SMS vs. WhatsApp vs. call). Velocity per kanál.
- **Funnel attribution** — který typ aktivity nejčastěji předchází `status_change`
  na *won*. Insight do toho, co reálně uzavírá obchod.
- **AI insights nad timeline** — `AiSummaryTool` jako automatický job: každý týden
  agreguj timeline leadu a navrhni next-best-action.

### 5.5 Integrace

- **Inbound webhook router** — generický endpoint `/inbound/{provider}/{kind}`,
  který podle providera (Twilio, Postmark, WhatsApp Cloud, DocuSign, Stripe…)
  routuje na správný `StreamlineTool` a vytvoří `Activity`. Sjednotí dnes
  roztříštěné webhook handlery.
- **Outbound provider abstraction** — jednotné rozhraní `MessageProvider` pro
  e-mail / SMS / WhatsApp / chat. `EmailOutTool` / `SmsOutTool` / `WhatsAppOutTool`
  by jen řekly „pošli", provider rozhodne podle config firmy.
- **Calendar two-way sync** — `MeetingScheduledTool` ↔ Google / Outlook
  Calendar (pull i push, přes ICS / CalDAV).
- **E-sign provider plugin** — `SignatureRequestedTool` jako adapter (DocuSign /
  SignWell / vlastní); `SignatureCompletedTool` se zaloguje webhook callbackem.

### 5.6 Performance / DX

- **`select_related` / `prefetch_related` audit** — jakmile timeline poroste,
  zkontrolovat N+1 dotazy v `ActivityOut` serializaci (zejména `user`, `tool_payload`,
  `reactions`).
- **Materialized view pro timeline** — pro velmi rušné entity (firmy s 10k+
  aktivit per lead) zvážit cache vrstvu / materializovaný feed v Redisu.
- **Retention policy per tool** — některé tooly (`entity_change`,
  `system_note`) lze po 6 měsících archivovat / agregovat. Konfigurovatelné
  per firma.
- **Bulk activity import API** — endpoint pro import historie z jiných CRM
  (Pipedrive, HubSpot) v batch módu, s explicit `created_at` override
  (dnes `auto_now_add`).

### 5.7 Bezpečnost / Compliance

- **GDPR export per entitní timeline** — endpoint, který pro daného `Customer`
  vrátí všechny aktivity (komentáře, e-maily, hovory, SMS…) v ZIPu.
- **GDPR delete / pseudonymizace** — bulk operace, která u kompletní timeline
  zákazníka přepíše PII (`user.email`, `metadata.to`, …) hashem nebo placeholderem.
- **Audit trail viewer** — admin UI nad `Activity` s filtrem na actor + date range
  (kdo co kdy v systému udělal).
- **Field-level encryption** pro citlivý `metadata` (např. `signer_email`,
  `provider_message_id`) — pgcrypto / `django-cryptography`.


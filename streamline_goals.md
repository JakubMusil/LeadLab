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

---

## 5. Future improvements *(parking lot — návrhy nad rámec současných 6 fází)*

> Nápady pro další iterace, jakmile bude Phase 0–6 v provozu. Žádný z nich není naléhavý,
> ale stojí za to je mít sepsané, ať na ně můžeme v budoucnu mrknout.

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


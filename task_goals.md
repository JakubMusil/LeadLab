# Task Enhancement Goals — Freelo-Inspired Roadmap

Tento dokument rozděluje požadované úpravy systému tasků do logických, postupně implementovatelných fází.
Inspirace: SaaS aplikace [Freelo](https://app.freelo.io) — propracovaný task management analyzovaný z detailu úkolu (screenshot + HTML Freelo task detail view).

---

## Kompletní přehled funkcí extrahovaných z Freela

Níže jsou všechny funkce nalezené v detailu úkolu Freela, rozdělené do tematických skupin.

### Identifikace a metadata
| Prvek | Popis |
|---|---|
| Sekvenční číslo úkolu | Každý task má viditelné `#ID` číslo pro snadné referencování |
| Název (inline editable) | Kliknutím na název lze přímo editovat bez otevření modálu |
| Popis (rich text) | Plnohodnotný rich-text editor pro popis (nikoliv jen plain text) |
| Priorita | 5 úrovní: žádná / nízká / střední / vysoká / kritická (s barevným kódováním) |
| Štítky/tagy | Barevně kódované tagy sdílené napříč projektem |
| Barva úkolu | Vizuální barevné označení celého úkolu (cover color) |
| Stav/status | todo / in-progress / done / cancelled / blocked (vlastní stavy) |
| Pozice/pořadí | Ruční řazení drag&dropem v seznamu |
| Viditelnost | Soukromý úkol (vidí jen přiřazení) nebo týmový |

### Přiřazení a termíny
| Prvek | Popis |
|---|---|
| Více přiřazených | Více assignee na jeden task (ne jen jeden) |
| Datum zahájení | Start date (od kdy) + due date (do kdy) — datum rozsah |
| Čas termínu | Přesný čas deadline (nejen datum) |
| Osobní připomenutí | Per-user reminder na konkrétní datum/čas |
| Pozorovatelé (watchers) | Sledující task bez nutnosti přiřazení |
| Schválení (approval) | Požádat konkrétní osobu o schválení; stav: čeká / schváleno / zamítnuto |

### Časové sledování
| Prvek | Popis |
|---|---|
| Odhad času | Budget hodin/minut na úkol |
| Logování odpracovaného času | Ručně zadat odpracovaný čas (datum + popis + hodiny) |
| Stopky (timer) | Start/stop timer přímo na detailu tasku; auto-přidá záznam po zastavení |
| Přehled strávený čas | Celkový čas logovaný všemi členy vs. budget (progress bar) |
| Historie logů | Seznam všech časových záznamů (kdo, kdy, kolik, popis) |

### Checklist a podtasky
| Prvek | Popis |
|---|---|
| Checklist | Rychlý interní checklist uvnitř tasku (ne plnohodnotné sub-tasky) |
| Podtasky (sub-tasks) | Plnohodnotné child tasky s vlastním detailem, timeline, přílohami |
| Progress sub-tasků | Vizuální progress bar X/Y dokončených podtasků |
| Breadcrumb navigace | Rodičovský task → podtask v hlavičce detailu |

### Závislosti a vazby
| Prvek | Popis |
|---|---|
| Blokuje | Task A blokuje Task B (dependency) |
| Blokován | Task A je blokován Task B |
| Kapcsolódik | Task je "related to" jiným taskem (bez blokování) |
| Vazba na entitu | Task vázaný na Lead / Nabídku / Zákazníka / samostatný |

### Přílohy a média
| Prvek | Popis |
|---|---|
| Upload souborů | Drag & drop nebo click-to-upload |
| Inline náhled obrázků | Obrázky se zobrazují jako galerie přímo v detailu |
| Stažení všech příloh | "Stáhnout vše jako ZIP" |
| Odkaz na přílohu | Přímý odkaz ke sdílení jednotlivého souboru |
| Náhled dokumentů | PDF viewer, video přehrávač přímo v detailu |

### Timeline a komentáře
| Prvek | Popis |
|---|---|
| Unified timeline | Komentáře + systémové události v jednom chronologickém feedu |
| Rich-text komentář | Tiptap editor s @mentions, tučné, kurzíva, seznamy, kód |
| Příloha ke komentáři | Přiložit soubor přímo ke komentáři |
| Emoji reakce | 👍❤️😄 reakce na komentáře (picker) |
| Odpověď na komentář | Reply threading — odpovědět na konkrétní komentář |
| Citace komentáře | Citovat část komentáře v odpovědi |
| Editace/smazání komentáře | Autor nebo admin může editovat/smazat |
| Systémové záznamy | Automatické záznamy: přiřazen, stav změněn, dokončen, termín změněn |
| Zmínky (@mentions) | @jméno upozorní konkrétního člena |
| Filtrování timeline | Zobrazit jen komentáře / jen systémové záznamy / vše |

### Operace nad taskem
| Prvek | Popis |
|---|---|
| Kopírovat task | Duplikovat task (s/bez podtasků, s/bez příloh) |
| Přesunout task | Přesunout na jiný projekt / entitu |
| Archivovat | Soft-delete: task zmizí ze seznamu, ale je dohledatelný |
| Smazat | Permanentní smazání (admin/vlastník) |
| Sdílet (public link) | Veřejný odkaz na task pro externího klienta (bez přihlášení) |
| Exportovat do PDF | Tisknout/exportovat detail tasku |
| Připnout | Pin task na začátek seznamu |
| Vytvořit šablonu | Uložit task jako šablonu pro opakované použití |
| Vytvořit z šablony | Vytvořit nový task z uložené šablony |
| Opakující se task | Nastavit recurrenci: denně / týdně / měsíčně / vlastní interval |

### Vlastní pole (Custom fields)
| Prvek | Popis |
|---|---|
| Textové pole | Libovolný text (poznámka, číslo zakázky, ...) |
| Číselné pole | Číslo s volitelnou jednotkou |
| Datum | Datové pole (jiné než termín) |
| Dropdown | Výběr z předdefinovaných hodnot |
| Checkbox | Ano/Ne pole |
| URL | Odkaz (zobrazí se jako klikatelný link) |
| Per-project konfigurace | Vlastní pole se definují na úrovni projektu / firmy |

### Zobrazení (Views)
| Prvek | Popis |
|---|---|
| Seznam (list) | Standardní řádkový seznam tasků |
| Kanban board | Sloupce dle stavu nebo priority, drag & drop |
| Ganttův diagram | Timeline zobrazení s datovými rozsahy a závislostmi |
| Kalendář | Tasky na kalendáři podle due date |
| Tabulka (table) | Tabulkové zobrazení se sloupci (jako spreadsheet) |
| Groupby | Seskupení dle: assignee / priorita / stav / štítek / vlastní pole |
| Filtr panel | Kombinovatelné filtry: stav, priorita, assignee, tagy, datum, vlastní pole |
| Uložené filtry / pohledy | Pojmenované sady filtrů (savedViews — základ existuje) |
| Batch akce | Vybrat více tasků → hromadné akce |

### Automatizace
| Prvek | Popis |
|---|---|
| Trigger: stav leadu/tasku | Automaticky vytvořit task při splnění podmínek |
| Akce: přiřadit uživatele | Pravidlo přiřadí task konkrétnímu členovi |
| Akce: nastavit deadline | Relativní deadline (N dní od triggeru) |
| Akce: přiřadit štítek | Automaticky přidat tag |
| Akce: přesunout task | Automaticky přesunout do jiného stavu/sloupce |
| Šablony placeholderů | `{{lead_title}}`, `{{customer_name}}`, `{{due_date}}` v názvech |
| Log spuštění | Historie všech spuštění pravidla (kdy, co se stalo) |

---

## Přehled požadavků (rozšířený)

| # | Požadavek | Složitost | Fáze |
|---|-----------|-----------|------|
| 1 | Task timeline — unified chronologický feed | Střední | 2 |
| 2 | Tasky nezávislé na Leadu + vazby na Proposal/Customer | Střední | 1 |
| 3 | Podtasky (hierarchie) + checklist uvnitř tasku | Střední | 3 |
| 4 | Závislosti mezi tasky (blokuje / blokován / related) | Střední | 3 |
| 5 | Pravidla pro automatické vytváření tasků (UI) | Střední | 4 |
| 6 | Priorita, štítky/tagy, barva, stav | Nízká | 1 |
| 7 | Více přiřazených + start date + osobní připomenutí | Nízká–Střední | 1 |
| 8 | Sledování času (odhad, log, timer/stopky) | Střední–Vysoká | 6 |
| 9 | Emoji reakce na komentáře + reply threading | Nízká | 2 |
| 10 | Opakující se tasky (recurrence) | Střední | 7 |
| 11 | Schválení (approval workflow) | Střední | 7 |
| 12 | Kopírovat / přesunout / archivovat task | Nízká | 5 |
| 13 | Public link na task (sdílení bez přihlášení) | Nízká | 5 |
| 14 | Šablony tasků | Střední | 7 |
| 15 | Vlastní pole (custom fields) per-firma | Vysoká | 8 |
| 16 | Kanban board view | Střední | 5 |
| 17 | Ganttův diagram | Vysoká | 8 |
| 18 | Tabulkový pohled | Střední | 8 |
| 19 | Inline náhled obrázků + download all ZIP | Nízká | 2 |
| 20 | Export tasku do PDF | Nízká | 5 |
| 21 | Sekvenční #ID číslo tasku | Nízká | 1 |
| 22 | Inline editace názvu (bez modálu) | Nízká | 2 |

---

## Fáze 1 — Flexibilní task entita + rozšířená metadata

**Cíl:** Task nemusí být nutně vázán na Lead. Může být vázán na Proposal, Customer, nebo existovat samostatně. Přidat všechna základní metadatová pole inspirovaná Freelem.

### Backend
- `Task.lead` — změnit z povinného FK na `null=True, blank=True`
- Přidat `Task.proposal` — nullable FK na `Proposal`
- Přidat `Task.customer` — nullable FK na `Customer`
- Přidat `Task.parent_task` — nullable self-FK pro podporu podtasků (příprava pro Fázi 3)
- Přidat `Task.priority` — CharField: `none / low / medium / high / critical` (default: `medium`)
- Přidat `Task.status` — CharField: `todo / in_progress / blocked / done / cancelled` (default: `todo`; doplňuje `is_completed`)
- Přidat `Task.tags` — JSONField (list of strings)
- Přidat `Task.color` — CharField(max_length=7, blank=True) — hex barva cover
- Přidat `Task.sequence_number` — PositiveIntegerField auto-inkrementovaný per-firma → viditelné `#ID`
- Přidat `Task.start_date` — DateTimeField(null=True, blank=True)
- Přidat `Task.description_html` — TextField(blank=True) — rich-text HTML popis
- Přidat `Task.is_private` — BooleanField(default=False)
- Přidat `Task.is_pinned` — BooleanField(default=False)
- Přidat `Task.is_archived` — BooleanField(default=False) — soft-delete
- Přidat `Task.assignees` — ManyToManyField (více přiřazených; zachovat `assigned_to` jako primární pro compat)
- Nový model `TaskReminder`: `id, task (FK), user (FK), remind_at, is_sent` — osobní připomenutí per-user
- Aktualizovat `TaskOut` schema a `_task_out()` helper
- Nová DB migrace

### Frontend
- `stores/tasks.ts`: rozšířit `TaskOut` o všechna nová pole
- `TaskDetailView.vue`:
  - Zobrazit `#sequence_number` v hlavičce
  - Inline editace názvu (klik → edit, Enter/Escape)
  - TipTap rich-text editor pro popis
  - Barevný chip priority + status badge
  - Datum rozsah: start + due date picker
  - Multi-assignee (avatary + přidat/odebrat)
  - Color/cover picker, přepínač private/public
- `TasksView.vue`: filtry podle entity, stavu, priority, tagů

---

## Fáze 2 — Unified task timeline + bohaté komentáře

**Cíl:** Místo oddělených sekcí "Komentáře" a "Přílohy" zobrazit jeden chronologický feed — jako v Freelu. Komentáře rozšířit o reakce, threading a citace.

### Backend
- Nový model `TaskTimelineEntry`:
  ```
  id, task (FK), author (FK),
  event_type: comment | file_upload | status_change | priority_change |
              assignee_change | due_date_change | sub_task_added |
              task_created | task_assigned | task_completed | task_archived |
              approval_requested | approval_resolved | time_logged | checklist_item_checked,
  content_html (blank), metadata (JSON), created_at
  ```
- Nový model `TaskCommentReaction`: `id, comment (FK na TaskTimelineEntry), user (FK), emoji (CharField)` — emoji reakce
- Nový model `TaskCommentReply` (nebo `parent_entry` self-FK na `TaskTimelineEntry`) — reply threading
- Při každé akci na tasku automaticky vytvořit systémový `TaskTimelineEntry`
- Endpoint `GET /api/v1/crm/tasks/{id}/timeline` → seřazený feed (filtrovatelný: `?type=comment|system|all`)
- Endpoint `POST /api/v1/crm/tasks/{id}/timeline` → přidat komentář s volitelnou přílohou (multipart)
- Endpoint `POST /api/v1/crm/tasks/{id}/timeline/{entry_id}/reactions` → přidat/odebrat emoji reakci
- Zachovat zpětnou kompatibilitu `/comments` a `/attachments` endpointů

### Frontend
- `TaskDetailView.vue`: nahradit oddělené sekce jedním `<TaskTimeline>` komponentem
- Timeline položky:
  - 💬 `comment` — rich-text + @mentions + inline přílohy (galerie obrázků) + emoji reakce + Reply tlačítko
  - 📎 `file_upload` — karta se souborem (náhled obrázku / ikona), stáhnout / smazat
  - 🔔 systémové záznamy — kompaktní řádek s ikonou a popisem změny
  - ↩️ reply threading — odpovědi zanořené pod rodičovský komentář
- Formulář nového komentáře: TipTap editor + drag&drop přílohy + Odeslat (Ctrl+Enter)
- Filtr timeline: "Vše / Komentáře / Systémové"
- Inline obrázková galerie (lightbox pro náhledy)
- "Stáhnout vše jako ZIP" tlačítko nad přílohami
- Inline editace názvu tasku (klik na název → input, Enter/Esc)

---

## Fáze 3 — Podtasky, checklist a závislosti

**Cíl:** Hierarchie tasků, interní checklist (rychlé položky bez plného detailu) a závislosti mezi tasky.

### Backend — Podtasky
- Využít `Task.parent_task` FK z Fáze 1
- Endpoint `GET /api/v1/crm/tasks/{id}/subtasks` → seznam přímých podtasků
- Endpoint `POST /api/v1/crm/tasks/{id}/subtasks` → vytvořit podtask
- `TaskOut` rozšířit o `subtask_count: int` a `subtasks_completed: int`
- Validace: max hloubka 3, žádné cyklické závislosti

### Backend — Checklist
- Nový model `TaskChecklistItem`: `id, task (FK), text, is_checked (bool), position, created_by (FK), created_at`
- Endpoint CRUD: `GET|POST /tasks/{id}/checklist`, `PATCH|DELETE /tasks/{id}/checklist/{item_id}`
- `TaskOut` rozšířit o `checklist_count: int` a `checklist_checked: int`

### Backend — Závislosti
- Nový model `TaskDependency`: `id, from_task (FK), to_task (FK), type (blocks | related_to)`
- Validace: žádné cyklické blokování
- Endpoint: `POST|DELETE /tasks/{id}/dependencies`

### Frontend
- `TaskDetailView.vue`:
  - Sekce "Podtasky" — progress bar + inline přidání + seznam s checkboxy + link na detail
  - Sekce "Checklist" — rychlé položky zaškrtávatelné inline, drag&drop řazení
  - Sekce "Závislosti" — "Blokuje:" / "Blokován:" / "Souvisí s:" + vyhledávání tasků pro přidání
  - Breadcrumb: Rodičovský task → aktuální task v hlavičce

---

## Fáze 4 — Automatická pravidla pro vytváření tasků

**Cíl:** Definovat pravidla: "Při [triggeru] s [podmínkami] vytvoř task [název] a přiřaď ho [uživateli]."

### Stav backendu
`AutomationRule` model s triggerem `create_task` akcí **již existuje**. Chybí pouze UI a rozšíření triggerů.

### Backend
- Přidat nové `AutomationTrigger` hodnoty:
  - `task_created` — při vytvoření tasku
  - `task_completed` — při dokončení tasku (pro řetězení)
  - `task_overdue` — již existuje
  - `proposal_accepted` — již existuje
- Akce `create_task` v `AutomationRule.actions` rozšířit o pole:
  - `title_template` — šablona s `{{lead_title}}`, `{{customer_name}}`, `{{due_date}}` placeholdery
  - `assign_to_user_id` — konkrétní uživatel nebo `"inherit"` (zdědí assignee triggeru)
  - `due_days_offset` — počet dní od triggeru
  - `priority` — priorita vytvářeného tasku
  - `tags` — automaticky přidat tagy
  - `parent_task_id` — volitelně vytvořit jako podtask
- Nová akce `set_task_status`: změní status existujícího tasku
- Nová akce `assign_tag`: přidá tag na task/lead

### Frontend
- Nová záložka "Pravidla tasků" v `SettingsView.vue` nebo `AutomationsView.vue`
- Formulář pro vytvoření pravidla:
  - Výběr triggeru (dropdown s popisem)
  - Podmínky (field + operator + value, přidávatelné řádky)
  - Akce: typ akce + parametry (dynamický formulář podle typu)
- Seznam pravidel s on/off přepínačem, datum posledního spuštění
- Log spuštění: rozbalitelný panel s historií posledních N spuštění (status, kdy, co se stalo)

---

## Fáze 5 — Operace nad taskem + Kanban + sdílení

**Cíl:** Základní UX operace (kopírovat, přesunout, archivovat, sdílet) + Kanban zobrazení.

### Backend
- Endpoint `POST /tasks/{id}/copy` → duplikovat task (parametry: `include_subtasks`, `include_attachments`, `include_checklist`)
- Endpoint `POST /tasks/{id}/move` → přesunout task na jinou entitu (lead_id / proposal_id / customer_id)
- Endpoint `POST /tasks/{id}/archive` a `POST /tasks/{id}/unarchive` — soft archivace
- Endpoint `GET /tasks/{id}/public-link` → generovat/vrátit public token (podobně jako u Proposals)
- Nový model `TaskPublicShare`: `id, task (FK), token (UUID), expires_at, created_by` — veřejný odkaz
- Veřejný endpoint `GET /public/tasks/{token}` — readonly náhled tasku bez auth
- Endpoint `POST /tasks/{id}/pin` a `POST /tasks/{id}/unpin`
- Filtrování v `GET /tasks`: přidat `?is_archived=true|false`, `?is_pinned=true`, `?status=...`, `?tags=...`

### Frontend
- `TaskDetailView.vue`: akční menu (⋮) s položkami:
  - Kopírovat task (modal s výběrem co kopírovat)
  - Přesunout task (výběr entity)
  - Archivovat / Obnovit z archivu
  - Sdílet (zkopírovat public link)
  - Exportovat do PDF
  - Připnout / Odepnout
  - Smazat (s potvrzením)
- `TasksView.vue`:
  - Přepínač **Seznam / Kanban / Tabulka**
  - Kanban: sloupce dle `status` (todo | in_progress | blocked | done | cancelled)
  - Drag & drop karet mezi sloupci (změní `status`)
  - Filtr panel: stav, priorita, assignee, tagy, datum, entita
  - Batch akce: checkbox výběr → hromadné dokončení / archivace / přiřazení / smazání
  - Archiv pohled: samostatný tab "Archivované"

---

## Fáze 6 — Sledování času (Time Tracking)

**Cíl:** Každý task může mít odhadovaný čas (budget) a zaznamenané odpracované hodiny. Stopky (timer) pro přesné měření.

### Backend
- Přidat `Task.estimated_minutes` — PositiveIntegerField(null=True) — odhad v minutách
- Nový model `TaskTimeLog`:
  ```
  id, task (FK), user (FK), logged_at (DateTimeField), duration_minutes (PositiveInt),
  description (TextField, blank), created_at
  ```
- Nový model `TaskTimer`: `id, task (FK), user (FK), started_at, stopped_at (null=running), created_at`
  - Constraint: jen jeden aktivní timer per user
- Endpointy:
  - `POST /tasks/{id}/time-logs` — zalogovat čas ručně
  - `GET /tasks/{id}/time-logs` — seznam záznamů
  - `DELETE /tasks/{id}/time-logs/{log_id}` — smazat záznam
  - `POST /tasks/{id}/timer/start` — spustit stopky
  - `POST /tasks/{id}/timer/stop` → zastaví timer + automaticky vytvoří `TaskTimeLog`
  - `GET /tasks/{id}/timer/active` — aktuální stav stopek pro přihlášeného uživatele
- `TaskOut` rozšířit o `estimated_minutes`, `total_logged_minutes`, `my_active_timer_started_at`
- Timeline entry `time_logged` při každém logu

### Frontend
- `TaskDetailView.vue`:
  - Sekce "Sledování času": progress bar (odpracováno / odhad), seznam logů
  - Stopky widget: Start/Stop tlačítko + zobrazení elapsed time (live update každou sekundu)
  - Formulář ručního logu: datum + hodiny + popis
  - Editace a smazání vlastních logů
- `TasksView.vue` / `TasksStore`: zobrazit `total_logged_minutes` ve sloupcích tabulky

---

## Fáze 7 — Pokročilé funkce (Opakující se tasky, Schválení, Šablony)

**Cíl:** Funkce pro pokročilejší workflow.

### Backend — Opakující se tasky
- Přidat `Task.recurrence` — JSONField:
  ```json
  {"type": "daily|weekly|monthly|custom", "interval": 1, "day_of_week": [1,3], "ends_at": null}
  ```
- Celery periodic task: každou půlnoc zkontrolovat `Task.recurrence` na dokončených opakujících se tascích a vytvořit novou instanci
- `TaskOut` rozšířit o `recurrence`, `recurrence_parent_id`

### Backend — Schválení (Approval)
- Přidat `Task.approval_required` — BooleanField(default=False)
- Přidat `Task.approval_requested_from` — FK na User
- Přidat `Task.approval_status` — CharField: `none / pending / approved / rejected`
- Přidat `Task.approval_note` — TextField (zdůvodnění zamítnutí)
- Endpoint `POST /tasks/{id}/request-approval` — požádat o schválení
- Endpoint `POST /tasks/{id}/approve` + `POST /tasks/{id}/reject` — schválení/zamítnutí
- Timeline entry při každé změně stavu schválení

### Backend — Šablony tasků
- Nový model `TaskTemplate` (TenantModel):
  ```
  id, firm (FK), name, description_html, priority, estimated_minutes,
  checklist_items (JSONField: [{text, position}]), tags (JSON), created_by (FK), created_at
  ```
- Endpoint CRUD: `GET|POST /task-templates`, `GET|PATCH|DELETE /task-templates/{id}`
- Endpoint `POST /task-templates/{id}/apply` → vytvoří nový Task z šablony (přijme `lead_id`/`proposal_id` + `assigned_to_id` + `due_date`)

### Frontend
- `TaskDetailView.vue`:
  - Recurrence picker (dropdown + interval + dny týdne)
  - Approval sekce: "Požádat o schválení" button + status badge + Schválit/Zamítnout (pro schvalovatele)
- `SettingsView.vue` nebo samostatná `TaskTemplatesView.vue`:
  - Seznam šablon s preview
  - Editor šablony (název, popis, checklist, priorita, odhad času)
- Při vytváření tasku: "Vytvořit ze šablony" tlačítko → modal s výběrem šablony

---

## Fáze 8 — Vlastní pole + Gantt + Tabulkový pohled

**Cíl:** Nejvyšší komplexita. Vlastní pole per-firma, Ganttův diagram a tabulkový pohled.

### Backend — Vlastní pole (Custom Fields)
- Nový model `TaskCustomField` (TenantModel):
  ```
  id, firm (FK), name, field_type (text|number|date|dropdown|checkbox|url),
  options (JSONField, pro dropdown), is_required (bool), position
  ```
- Nový model `TaskCustomFieldValue`:
  ```
  id, task (FK), field (FK na TaskCustomField), value_text, value_number,
  value_date, value_bool, created_at, updated_at
  ```
- Endpointy: CRUD `/custom-fields`, `PATCH /tasks/{id}/custom-fields` (bulk upsert hodnot)
- `TaskOut` rozšířit o `custom_fields: [{field_id, name, type, value}]`

### Frontend — Vlastní pole
- `SettingsView.vue`: správa custom fields (přidat/upravit/smazat/přeuspořádat)
- `TaskDetailView.vue`: sekce "Vlastní pole" s dynamickými inputy (text, number, date picker, dropdown, checkbox, URL)

### Frontend — Ganttův diagram
- Nová záložka "Gantt" v `TasksView.vue`
- Použít knihovnu `dhtmlx-gantt` nebo `frappe-gantt` (MIT licence)
- Řádky = tasky, osy X = čas, vizualizace start_date → due_date
- Závislosti (šipky) mezi tasky dle `TaskDependency`
- Drag & drop pro posun termínů

### Frontend — Tabulkový pohled
- Záložka "Tabulka" v `TasksView.vue`
- Spreadsheet-like: řádky = tasky, sloupce = task fields (konfigurovatelné)
- Inline editace buněk (kliknutím)
- Řazení podle libovolného sloupce
- Skupiny (group by assignee / priority / status / tag)

---

## Doporučené pořadí implementace

```
Fáze 1 → Fáze 3 → Fáze 2 → Fáze 5 → Fáze 4 → Fáze 6 → Fáze 7 → Fáze 8
```

| Fáze | Název | Závisí na | Dopad |
|------|-------|-----------|-------|
| 1 | Flexibilní entita + rozšířená metadata | — | ⭐⭐⭐ základ pro vše |
| 3 | Podtasky + checklist + závislosti | 1 | ⭐⭐⭐ klíčová funkce |
| 2 | Unified timeline + bohaté komentáře | 1 | ⭐⭐⭐ UX zásadní změna |
| 5 | Kanban + operace (kopír., archiv, sdílení) | 1, 2 | ⭐⭐ viditelné zlepšení |
| 4 | Automation rules UI | 1 | ⭐⭐ backend hotový |
| 6 | Sledování času + timer | 1, 2 | ⭐⭐ pokročilá funkce |
| 7 | Opakující se tasky + approval + šablony | 1, 2, 3 | ⭐⭐ pokročilý workflow |
| 8 | Custom fields + Gantt + tabulka | 1–7 | ⭐ enterprise funkce |

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
| Task nezávislý na Leadu | ❌ Chybí (Fáze 1) |
| Sekvenční `#ID`, inline edit názvu, `status`, `priority`, `tags`, `color` | ❌ Chybí (Fáze 1) |
| Více assignee, start_date, soukromý task, archivace, připnutí | ❌ Chybí (Fáze 1) |
| `TaskReminder` — osobní připomenutí | ❌ Chybí (Fáze 1) |
| Rich-text popis (`description_html`) | ❌ Chybí (Fáze 1) |
| Podtasky (`parent_task` FK) | ❌ Chybí (Fáze 3) |
| `TaskChecklistItem` — interní checklist | ❌ Chybí (Fáze 3) |
| `TaskDependency` — závislosti (blokuje/blokován/related) | ❌ Chybí (Fáze 3) |
| Unified timeline (`TaskTimelineEntry`) | ❌ Chybí (Fáze 2) |
| Emoji reakce na komentáře (`TaskCommentReaction`) | ❌ Chybí (Fáze 2) |
| Reply threading na komentáře | ❌ Chybí (Fáze 2) |
| Inline galerie + download all ZIP | ❌ Chybí (Fáze 2) |
| Kanban board pohled | ❌ Chybí (Fáze 5) |
| Kopírovat / přesunout / archivovat task | ❌ Chybí (Fáze 5) |
| Public link na task | ❌ Chybí (Fáze 5) |
| Export tasku do PDF | ❌ Chybí (Fáze 5) |
| Pravidla tasků UI | ❌ Chybí (Fáze 4) |
| `TaskTimeLog` + `TaskTimer` (stopky) | ❌ Chybí (Fáze 6) |
| Opakující se tasky (recurrence) | ❌ Chybí (Fáze 7) |
| Approval workflow | ❌ Chybí (Fáze 7) |
| `TaskTemplate` — šablony tasků | ❌ Chybí (Fáze 7) |
| `TaskCustomField` — vlastní pole | ❌ Chybí (Fáze 8) |
| Ganttův diagram | ❌ Chybí (Fáze 8) |
| Tabulkový pohled | ❌ Chybí (Fáze 8) |

# Task Enhancement Goals — Freelo-Inspired Roadmap

Tento dokument rozděluje požadované úpravy systému tasků do logických, postupně implementovatelných fází.
Inspirace: SaaS aplikace [Freelo](https://app.freelo.io) — propracovaný task management analyzovaný z detailu úkolu (3 screenshoty Freelo task detail view).

---

## Kompletní přehled funkcí extrahovaných z Freela

Níže jsou všechny funkce nalezené v detailu úkolu Freela, rozdělené do tematických skupin.

### Identifikace a metadata
| Prvek | Popis | Vidět ve screenshotu |
|---|---|---|
| Název (inline editable, strikethrough) | Kliknutím na název lze přímo editovat; dokončený task má přeškrtnutý název | ✅ SS1/2/3 |
| Popis úkolu (rich text, labeled section) | Sekce "Popis úkolu" — samostatný blok před komentáři, s timestampem přidání | ✅ SS3 |
| Breadcrumb navigace | "Firma > Úkoly > Projekt" v hlavičce — 3-úrovňová hierarchie | ✅ SS1/2/3 |
| Metadata vytvoření a dokončení | "Vytvořil [jméno] [datum]  \|  Dokončil [jméno] [datum]" — bar pod hlavičkou | ✅ SS3 |
| Stav/status (zaškrtnutí) | Modrý checkbox vlevo od názvu — kliknutím přepne dokončeno/nedokončeno | ✅ SS1/2/3 |
| Priorita | Nastavit... s ikonou trojúhelníku/vlajky; výběr z úrovní | ✅ sidebar |
| Štítky/tagy | Nastavit... s ikonou štítku | ✅ sidebar |
| Projekty (multi-project) | Task lze přiřadit k více projektům: "+ Přidat..." v sidebaru | ✅ sidebar |
| Vlastní pole | "+ Přidat..." v sidebaru — custom fields per-firma | ✅ sidebar |
| Vazby | "+ Přidat..." v sidebaru — relations/dependencies | ✅ sidebar |

### Hlavičkový action bar (ikony vedle názvu)
| Ikona | Akce |
|---|---|
| ▷ (Play) | Rychlý start stopek (timer) přímo z hlavičky |
| 📅 (Calendar) | Rychlý přístup k nastavení termínu |
| 🏷️ (Tag) | Rychlé přidání štítku |
| ⚠️ (Triangle) | Rychlé nastavení priority |
| ⋮ (More) | Rozbalovací menu dalších akcí |
| ⭐ (Star) | Oblíbit / přidat do oblíbených (top-right sidebar) |
| ↺ (Recurrence) | Indikátor / nastavení opakování (top-right sidebar) |
| 👁️ (Eye) | Sledovat / přestat sledovat task (top-right sidebar) |
| 🔗 (Link) | Zkopírovat přímý odkaz na task (top-right sidebar) |

### Přiřazení a termíny
| Prvek | Popis | Vidět ve screenshotu |
|---|---|---|
| Řešitel (jeden) | **Jeden primární** "Řešitel" s avatarem v sidebaru — ne multi-assignee | ✅ sidebar |
| Sledující (watchers, více) | "Sledující" — několik avatarů + tlačítko přidat; zobrazeni i pod formulářem komentáře | ✅ SS1/2/3 |
| Termín(y) — date range | "Termín(y)" v sidebaru (plurál) — toggle "Rozsah termínů" zapne start+end datum | ✅ SS2 date picker |
| Vybrat čas k termínu | Toggle "Vybrat čas" v date pickeru — přidá časový vstup k datu | ✅ SS2 |
| Date picker s týdny | Kalendář zobrazuje čísla týdnů (sloupec "Týd.") vlevo | ✅ SS2 |
| Zrušit termín | Tlačítko "Zrušit termín(y)" v date pickeru — odstraní termín | ✅ SS2 |

### Časové sledování
| Prvek | Popis | Vidět ve screenshotu |
|---|---|---|
| Výkazy (time reports) | Sidebar sekce "Výkazy" s ikonou ▷ i ⏱️ — dva způsoby přidání (timer i manuálně) | ✅ sidebar |
| Odhad | Sidebar sekce "Odhad" — "+ Přidat..." — budget hodin | ✅ sidebar |
| Stopky z hlavičky | ▷ v action baru — rychlý start stopek bez otevření sekce | ✅ SS1 header |

### Podtasky a checklist
| Prvek | Popis | Vidět ve screenshotu |
|---|---|---|
| "+ Přidat podúkoly ▼" | Zelené tlačítko s dropdown šipkou nad popisem tasku | ✅ SS3 |
| Dropdown podúkolů | Šipka naznačuje volby při přidání (prázdný / ze šablony) | ✅ SS3 |

### Přílohy a média
| Prvek | Popis | Vidět ve screenshotu |
|---|---|---|
| Příloha v komentáři | Soubory přiložené ke komentáři: barevná ikona typu (zelená XLS), název, autor, datum, velikost | ✅ SS1/2/3 |
| Kontextové menu přílohy | Ikona ⋮ na každé příloze — stáhnout, smazat, sdílet odkaz | ✅ SS1/2 |
| Inline obrázky v komentářích | Screenshot/obrázek se zobrazí jako embedded náhled přímo v komentáři | ✅ SS3 |

### Timeline a komentáře
| Prvek | Popis | Vidět ve screenshotu |
|---|---|---|
| Unified timeline | Popis úkolu (jako první položka) + komentáře + přílohy v jednom scrollovatelném feedu | ✅ SS3 |
| Řazení komentářů | "↑↓ Nejnovější dole" — toggle pro změnu směru řazení | ✅ SS3 |
| Timestamp komentáře | Avatar + jméno + "Přidáno [datum] v [čas]" pod každým komentářem | ✅ SS2/3 |
| Comment placeholder | "Přidej komentář, řešitele, sledující, ..." — smart input, @-mention přidá i watcher | ✅ SS2/3 |
| "Sledující:" pod inputem | Avatary sledujících zobrazeny přímo pod formulářem komentáře | ✅ SS2/3 |

### Formulář komentáře (editor toolbar)
| Prvek | Popis |
|---|---|
| Tučné, kurzíva, přeškrtnutí | **B** *I* S |
| Odkaz | 🔗 — vložit hyperlink |
| Zvýraznění/marker | ✏️ — highlight textu |
| Citace (blockquote) | " — citát |
| Kód (inline/block) | `</>` — kód |
| Seznamy | ≡ nečíslovaný + ≡ číslovaný |
| Přiložit soubor | 📎 "Přiložit soubor" — click-to-upload příloha ke komentáři |
| Zpět / Vpřed | ← → — undo/redo |
| Hlasová zpráva | 🎤 — nahrát hlasovou zprávu a přiložit ke komentáři |
| Video zpráva | 📹 — nahrát nebo nahrát video ke komentáři |
| Emoji v textu | 😊 — vložit emoji do textu komentáře |

### "Upozornění dostávají" panel v editoru komentáře
| Prvek | Popis |
|---|---|
| Zobrazení příjemců | Avatary všech, kdo dostávají upozornění na tento task |
| Toggle "Změnit řešitele..." | Při uložení komentáře zároveň změnit Řešitele na jmenovanou osobu |
| Toggle "Vykázat..." | Při uložení komentáře zároveň zalogovat čas (vyplnit výkaz) |
| Toggle "Změnit termín..." | Při uložení komentáře zároveň nastavit nový termín (zobrazí se aktuální datum) |
| "Uložit" s dropdown šipkou | Primární tlačítko + dropdown naznačuje alternativní možnosti uložení |

### Závislosti a vazby
| Prvek | Popis |
|---|---|
| Blokuje | Task A blokuje Task B |
| Blokován | Task A je blokován Task B |
| Souvisí s | "Related to" — volné propojení bez blokování |
| Vazba na entitu | Task vázaný na Lead / Nabídku / Zákazníka / samostatný |

### Operace nad taskem
| Prvek | Popis |
|---|---|
| Oblíbit (⭐) | Přidat task do osobních oblíbených |
| Sledovat (👁️) | Přihlásit se / odhlásit z notifikací na task |
| Kopírovat přímý odkaz (🔗) | Zkopírovat URL na task do schránky |
| Kopírovat task | Duplikovat (s/bez podtasků, příloh) |
| Přesunout task | Přesunout na jiný projekt / entitu |
| Archivovat | Soft-delete |
| Smazat | Permanentní smazání |
| Sdílet (public link) | Veřejný odkaz bez přihlášení |
| Exportovat do PDF | Tisknout / exportovat |
| Připnout | Pin na začátek seznamu |
| Opakující se task | Nastavit recurrenci |
| Vytvořit šablonu / ze šablony | Uložit nebo použít šablonu |

### Vlastní pole (Custom fields)
| Prvek | Popis |
|---|---|
| Textové pole | Libovolný text |
| Číselné pole | Číslo s volitelnou jednotkou |
| Datum | Datové pole |
| Dropdown | Výběr z předdefinovaných hodnot |
| Checkbox | Ano/Ne |
| URL | Klikatelný odkaz |
| Per-firma konfigurace | Definují se na úrovni firmy/projektu |

### Zobrazení (Views)
| Prvek | Popis |
|---|---|
| Seznam (list) | Standardní řádkový seznam |
| Kanban board | Sloupce dle stavu, drag & drop |
| Ganttův diagram | Timeline s rozsahy a závislostmi |
| Kalendář | Tasky dle due date v kalendáři |
| Tabulka (spreadsheet) | Sloupce = task fields, inline editace |
| Groupby | Seskupení dle assignee / priorita / stav / tag |
| Filtr panel | Kombinovatelné filtry |
| Uložené pohledy | Pojmenované sady filtrů |
| Batch akce | Hromadné operace nad vybranými tasky |

### Automatizace
| Prvek | Popis |
|---|---|
| Trigger: stav leadu/tasku | Automaticky vytvořit task |
| Akce: přiřadit řešitele | Přiřadit task uživateli |
| Akce: nastavit deadline | Relativní deadline (N dní od triggeru) |
| Akce: přiřadit štítek | Přidat tag |
| Akce: přesunout task | Změnit stav/sloupec |
| Šablony placeholderů | `{{lead_title}}`, `{{customer_name}}`, `{{due_date}}` |
| Log spuštění | Historie spuštění pravidla |

---

## Přehled požadavků (rozšířený)

| # | Požadavek | Složitost | Fáze |
|---|-----------|-----------|------|
| 1 | Task timeline — unified chronologický feed + řazení komentářů | Střední | 2 |
| 2 | Tasky nezávislé na Leadu + vazby na Proposal/Customer + multi-project | Střední | 1 |
| 3 | Podtasky — "Přidat podúkoly ▼" button + dropdown (prázdný / ze šablony) | Střední | 3 |
| 4 | Checklist uvnitř tasku | Nízká | 3 |
| 5 | Závislosti mezi tasky (blokuje / blokován / related) | Střední | 3 |
| 6 | Pravidla pro automatické vytváření tasků (UI) | Střední | 4 |
| 7 | Priorita, štítky/tagy, stav (sidebar + quick-access ikony v header) | Nízká | 1 |
| 8 | Řešitel (jeden) + Sledující (watchers M2M) | Nízká | 1 |
| 9 | Termín s date range toggle + "Vybrat čas" toggle + čísla týdnů | Nízká | 1 |
| 10 | Metadata bar: Vytvořil / Dokončil (jméno + datum) | Nízká | 1 |
| 11 | Sekce "Popis úkolu" s TipTap editorem + timestamp přidání | Nízká | 1 |
| 12 | Sledování času: Výkazy (timer ▷ + manuál ⏱️) + Odhad v sidebaru | Střední–Vysoká | 6 |
| 13 | Formulář komentáře: B/I/S/link/highlight/quote/code/list + 📎/🎤/📹/😊 | Nízká | 2 |
| 14 | "Upozornění dostávají" panel v editoru + action toggles (řešitel / čas / termín) | Střední | 2 |
| 15 | "Přidej komentář, řešitele, sledující, ..." smart placeholder | Nízká | 2 |
| 16 | Řazení komentářů toggle "↑↓ Nejnovější dole" | Nízká | 2 |
| 17 | Inline obrázky v komentářích (embedded náhled) | Nízká | 2 |
| 18 | Příloha: barevná ikona typu, název, autor, datum, velikost, ⋮ menu | Nízká | 2 |
| 19 | Header action bar ikony: ▷ 📅 🏷️ ⚠️ ⋮ | Nízká | 2 |
| 20 | Sidebar top-right ikony: ⭐ ↺ 👁️ 🔗 | Nízká | 5 |
| 21 | Emoji reakce na komentáře + reply threading | Nízká | 2 |
| 22 | Opakující se tasky (recurrence) | Střední | 7 |
| 23 | Schválení (approval workflow) | Střední | 7 |
| 24 | Kopírovat / přesunout / archivovat task | Nízká | 5 |
| 25 | Public link na task (sdílení bez přihlášení) | Nízká | 5 |
| 26 | Šablony tasků | Střední | 7 |
| 27 | Vlastní pole (custom fields) per-firma | Vysoká | 8 |
| 28 | Kanban board view | Střední | 5 |
| 29 | Ganttův diagram | Vysoká | 8 |
| 30 | Tabulkový pohled | Střední | 8 |
| 31 | Export tasku do PDF | Nízká | 5 |
| 32 | Hlasové a video zprávy v komentářích | Střední | 2 |

---

## Fáze 1 — Flexibilní task entita + rozšířená metadata

**Cíl:** Task nemusí být nutně vázán na Lead. Může být vázán na Proposal, Customer, nebo existovat samostatně. Přidat všechna základní metadatová pole potvrzená screenshoty Freela.

### Backend
- `Task.lead` — změnit z povinného FK na `null=True, blank=True`
- Přidat `Task.proposal` — nullable FK na `Proposal`
- Přidat `Task.customer` — nullable FK na `Customer`
- Přidat `Task.parent_task` — nullable self-FK (příprava pro Fázi 3)
- Přidat `Task.priority` — CharField: `none / low / medium / high / critical` (default: `medium`)
- Přidat `Task.status` — CharField: `todo / in_progress / blocked / done / cancelled` (default: `todo`; doplňuje `is_completed` boolean)
- Přidat `Task.tags` — JSONField (list of strings)
- Přidat `Task.is_pinned` — BooleanField(default=False)
- Přidat `Task.is_archived` — BooleanField(default=False) — soft-delete
- Přidat `Task.is_favourite` — BooleanField(default=False) per-user přes M2M (viz níže)
- Přidat `Task.description_html` — TextField(blank=True) — TipTap rich-text HTML; zobrazuje se jako sekce "Popis úkolu" s timestampem přidání
- Přidat `Task.description_added_at` — DateTimeField(null=True) — kdy byl popis přidán/naposledy upraven
- **Řešitel**: `Task.assigned_to` (stávající FK) = primární "Řešitel" — **jeden uživatel** (jak ukazuje screenshot sidebar)
- **Sledující**: `Task.watchers` (stávající M2M) — "Sledující" zobrazeni v sidebaru i pod formulářem komentáře
- Přidat `Task.due_date` s podporou rozsahu: přidat `Task.due_date_end` — DateTimeField(null=True) — toggle "Rozsah termínů"
- Přidat `Task.projects` — ManyToManyField na `Project` (task lze přiřadit k více projektům — potvrzeno v sidebaru "Projekty")
- Nový model `TaskFavourite`: `id, task (FK), user (FK)` — per-user oblíbené (⭐)
- Nový model `TaskReminder`: `id, task (FK), user (FK), remind_at, is_sent` — osobní připomenutí
- Aktualizovat `TaskOut` schema a `_task_out()` helper
- Nová DB migrace

### Frontend
- `stores/tasks.ts`: rozšířit `TaskOut` o všechna nová pole
- `TaskDetailView.vue`:
  - **Breadcrumb** v hlavičce: "Firma > Úkoly > Projekt"
  - **Metadata bar** pod hlavičkou: "Vytvořil [jméno] [datum] | Dokončil [jméno] [datum]"
  - **Název**: přeškrtnutý pokud `is_completed`; klik → inline edit, Enter/Escape
  - **Modrý checkbox** vlevo od názvu — kliknutí přepíná `is_completed`
  - **Header action bar** vpravo od názvu: `▷` (timer) `📅` (termín) `🏷️` (štítek) `⚠️` (priorita) `⋮` (více)
  - **Sidebar top-right** ikony: `⭐` oblíbit, `↺` recurrence, `👁️` sledovat, `🔗` kopírovat odkaz
  - **Sidebar pole** (s "+ Přidat..." / "Nastavit..." pro každé):
    - Řešitel (avatar + jméno)
    - Sledující (avatary + přidat)
    - Termín(y) (date picker s week numbers, range toggle, time toggle)
    - Projekty (multi-project přiřazení)
    - Priorita
    - Štítky
    - Výkazy (▷ timer + ⏱️ manuální log)
    - Odhad
    - Vlastní pole
    - Vazby
  - **"Popis úkolu" sekce**: TipTap rich-text editor, zobrazuje "(Přidáno [datum])" footer
  - **Date picker**: měsíční grid + čísla týdnů (sloupec "Týd."), toggle "Rozsah termínů", toggle "Vybrat čas", tlačítka "Uložit" + "Zrušit termín(y)"
- `TasksView.vue`: filtry podle entity, stavu, priority, tagů, oblíbených

---

## Fáze 2 — Unified task timeline + bohaté komentáře

**Cíl:** Jeden chronologický feed (popis → komentáře → systémové záznamy). Formulář komentáře s plným toolbarem, hlasovými/video zprávami, "Upozornění dostávají" panelem a action toggles.

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
- Nový model `TaskCommentReaction`: `id, comment (FK na TaskTimelineEntry), user (FK), emoji (CharField)`
- Self-FK `TaskTimelineEntry.parent_entry` — reply threading
- Nový model `TaskVoiceAttachment`: `id, timeline_entry (FK), file_field, duration_seconds` — hlasová zpráva
- Endpoint `GET /api/v1/crm/tasks/{id}/timeline?type=all|comment|system&order=asc|desc` — feed s filtrováním a řazením
- Endpoint `POST /api/v1/crm/tasks/{id}/timeline` — přidat komentář (multipart: content_html + soubory)
- Endpoint `POST /api/v1/crm/tasks/{id}/timeline/{entry_id}/reactions`
- Komentář může zároveň provést side-effects (z "action toggles"):
  - `change_assignee_to` — přeřadit Řešitele
  - `log_time` — přidat `TaskTimeLog` záznam
  - `set_due_date` — nastavit termín
- Zachovat zpětnou kompatibilitu `/comments` a `/attachments`

### Frontend — `<TaskTimeline>` komponenta
- Nahradit oddělené sekce jedním chronologickým feedem
- Jako **první položka** feed zobrazí "Popis úkolu" sekci (z Fáze 1) s timestampem
- **Řazení toggle**: "↑↓ Nejnovější dole" — kliknutím přepíná asc/desc (default: nejnovější dole)
- Timeline typy:
  - 💬 `comment` — rich-text + inline obrázky (embedded) + přílohy (barevná ikona typu, název, autor, datum, velikost, ⋮ menu) + emoji reakce + Reply
  - 🔔 systémové záznamy — kompaktní řádek s ikonou
- **Formulář nového komentáře**:
  - Placeholder: "Přidej komentář, řešitele, sledující, ..." (@-mention přidá watcher)
  - **Toolbar**: **B** *I* S 🔗 ✏️ " `</>` ≡ ≡ | 📎 Přiložit soubor | ← → | 🎤 hlasová zpráva | 📹 video zpráva | 😊 emoji v textu
  - Drag & drop přílohy do editoru
  - **"Upozornění dostávají" panel** (rozbalitelný pod editorem):
    - Zobrazení avatarů příjemců upozornění
    - Toggle "Změnit řešitele... [aktuální jméno]" — změní Řešitele při uložení
    - Toggle "Vykázat..." — otevře mini-formulář pro log času
    - Toggle "Změnit termín... [aktuální datum]" — přepíše termín při uložení
  - Tlačítko **"Uložit ▼"** (dropdown šipka) + "Zrušit"
  - Klávesová zkratka: Ctrl+Enter pro odeslání
- **"Sledující:"** sekce pod formulářem — avatary všech sledujících
- **Přílohy**: každá s barevnou ikonou typu souboru (zelená XLS, modrá DOC, ...), ⋮ kontextové menu (stáhnout / smazat / kopírovat odkaz)
- **Inline obrázky** v komentářích — renderovat jako embedded náhled (ne jako attachment karta)
- "Stáhnout vše jako ZIP" tlačítko

---

## Fáze 3 — Podtasky, checklist a závislosti

**Cíl:** Hierarchie tasků, interní checklist a závislosti. Freelo zobrazuje prominentní "**+ Přidat podúkoly ▼**" zelené tlačítko s dropdown šipkou hned pod metadata barem — to je výchozí vstupní bod pro přidání podtasku.

### Backend — Podtasky
- Využít `Task.parent_task` FK z Fáze 1
- Endpoint `GET /api/v1/crm/tasks/{id}/subtasks` → seznam přímých podtasků
- Endpoint `POST /api/v1/crm/tasks/{id}/subtasks` → vytvořit podtask; dropdown parametr `from_template_id` (ze šablony)
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
  - **"+ Přidat podúkoly ▼"** zelené tlačítko s dropdown šipkou pod metadata barem — dropdown: "Prázdný podúkol" / "Ze šablony"
  - Sekce "Podtasky" — progress bar (X/Y dokončeno) + seznam s checkboxy + link na detail
  - Sekce "Checklist" — položky inline zaškrtávatelné, drag&drop řazení
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
| `Task.watchers` / Sledující (M2M) | ✅ Hotovo |
| `TaskDetailView.vue` (komentáře + přílohy, oddělené sekce) | ✅ Hotovo (nahradit Fází 2) |
| `TasksView.vue` (seznam + filtrování) | ✅ Hotovo |
| Follow-up task po dokončení | ✅ Hotovo |
| `AutomationRule` s `create_task` akcí | ✅ Backend hotovo |
| **Fáze 1** | |
| Task nezávislý na Leadu, vazba na Proposal/Customer, multi-project | ❌ Chybí |
| Breadcrumb, metadata bar (Vytvořil/Dokončil), přeškrtnutý název | ❌ Chybí |
| `status`, `priority`, `tags`, `is_pinned`, `is_archived`, `is_favourite` | ❌ Chybí |
| `description_html` + `description_added_at` (sekce "Popis úkolu") | ❌ Chybí |
| `due_date_end` (Rozsah termínů) + date picker s week numbers + Vybrat čas | ❌ Chybí |
| `Task.projects` M2M (multi-project) | ❌ Chybí |
| `TaskFavourite` model (⭐ oblíbit) | ❌ Chybí |
| `TaskReminder` model (osobní připomenutí) | ❌ Chybí |
| Sidebar s 10 poli (Řešitel, Sledující, Termíny, Projekty, Priorita, Štítky, Výkazy, Odhad, Vlastní pole, Vazby) | ❌ Chybí |
| Header action bar ikony (▷ 📅 🏷️ ⚠️ ⋮) | ❌ Chybí |
| Sidebar top-right ikony (⭐ ↺ 👁️ 🔗) | ❌ Chybí |
| **Fáze 2** | |
| Unified timeline (`TaskTimelineEntry`) | ❌ Chybí |
| Řazení komentářů toggle (↑↓ Nejnovější dole) | ❌ Chybí |
| TipTap toolbar: B/I/S/link/highlight/quote/code/list + 📎/🎤/📹/😊 | ❌ Chybí |
| "Upozornění dostávají" panel + action toggles (řešitel/čas/termín) | ❌ Chybí |
| "Uložit ▼" s dropdown + side-effects při uložení komentáře | ❌ Chybí |
| Smart placeholder "Přidej komentář, řešitele, sledující, ..." | ❌ Chybí |
| Emoji reakce (`TaskCommentReaction`) | ❌ Chybí |
| Reply threading (self-FK na `TaskTimelineEntry`) | ❌ Chybí |
| Inline obrázky embedded v komentářích | ❌ Chybí |
| Příloha: barevná ikona, autor, datum, velikost, ⋮ menu | ❌ Chybí |
| Hlasové zprávy (🎤) a video zprávy (📹) v komentářích | ❌ Chybí |
| Download all ZIP | ❌ Chybí |
| **Fáze 3** | |
| `parent_task` FK + "Přidat podúkoly ▼" button s dropdown | ❌ Chybí |
| `TaskChecklistItem` — interní checklist | ❌ Chybí |
| `TaskDependency` — závislosti (blokuje/blokován/related) | ❌ Chybí |
| **Fáze 4** | |
| Pravidla tasků UI (AutomationsView) | ❌ Chybí |
| **Fáze 5** | |
| Kanban board pohled | ❌ Chybí |
| Kopírovat / přesunout / archivovat task | ❌ Chybí |
| Public link na task (`TaskPublicShare`) | ❌ Chybí |
| Export tasku do PDF | ❌ Chybí |
| **Fáze 6** | |
| `TaskTimeLog` + `TaskTimer` (stopky, Výkazy sidebar) | ❌ Chybí |
| **Fáze 7** | |
| Opakující se tasky (recurrence) | ❌ Chybí |
| Approval workflow | ❌ Chybí |
| `TaskTemplate` — šablony + "Ze šablony" v dropdown podúkolů | ❌ Chybí |
| **Fáze 8** | |
| `TaskCustomField` + `TaskCustomFieldValue` (Vlastní pole sidebar) | ❌ Chybí |
| Ganttův diagram | ❌ Chybí |
| Tabulkový pohled (spreadsheet) | ❌ Chybí |

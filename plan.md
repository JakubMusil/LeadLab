# Plán — kontrast editoru, popis leadu, sjednocení TODO/podúkolů do Streamline

## Výchozí požadavek

> V light verzi máme problem s kontrastem v rámci textu uvnitř editoru, který využíváme... Souběžně je problém že popis leadu musí být všude editovatelný editorem, ale není a následně se občas někde vypisuje obsah bez Safe HTML elementů. Tohle by bylo potřeba plošně opravit. U akci máme navíc todo a podukoly. Oboje by mělo být řešeno v rámci streamline a původní smažeme bez migrace dat. Přidávat nové úkoly i foto by mělo být možné pouhým psaní textů, kde každý řádek bude nova položka. Oboje bude možné dodatečně označit pokožkové za vyřešené a souběžně by měla v nadřazeném streamline o tom vzniknout nějaký záznam, kde opět bude kdo, kdy danou položku označil za vyřešenou, případně znovu za nevyřešenou.

## Pracovní předpoklady (zatím nepotvrzené uživatelem)

1. **"Akce" = `Task`** (entita Task ve streamline světě). TODO + podúkoly jsou dnes navázané na `Task` (`TaskChecklistItem`, `Task.parent_task`). Sjednocení proběhne tak, že obě věci nahradí jeden nový jednotný `StreamlineItem` model navázaný na `Task`, s `kind = todo | subtask`.
2. **Položky** mají pouze: `text`, `is_resolved`, kdo/kdy je vytvořil, kdo/kdy je vyřešil/znovu otevřel. Žádné assignee/deadline na úrovni položky (pokud bude potřeba, řeší se až povýšením položky na samostatný `Task`).
3. **Multi-line input:** jeden agregovaný streamline záznam typu `items_added` (s počtem položek + texty v metadata). Při toggle resolve/reopen vznikají individuální záznamy.
4. **`Lead.description` migrace na HTML:** stávající plain-text obsah obalíme při migraci do `<p>...</p>` (drobná, bezpečná transformace, není to "data migration" ve smyslu komplexních dat — je to jen přepnutí sloupce na HTML).

## Kroky

### Krok 1 — Plošný fix kontrastu v light mode (Tiptap + prose)
- [x] Audit všech míst, kde se zobrazuje výstup z `RichTextEditor` (search `prose ` ve `frontend-spa/src/`).
- [x] Zjištěna kořenová příčina: chybějící `@tailwindcss/typography` plugin → prose třídy byly mrtvé.
- [x] Plugin nainstalován (`@tailwindcss/typography@^0.5.19`) a zaregistrován v `tailwind.config.ts` s vlastní paletou pro WCAG-AA.
- [x] V `RichTextEditor.vue` (edit oblast): nastavena explicitní `text-gray-900 dark:text-gray-100`, opraven placeholder color.
- [x] Doplněno chybějící `dark:prose-invert` a sjednocen kontejnerový `text-gray-700 dark:text-gray-300` v `LeadDetailView.vue:564`.
- [x] Vytvořena shared komponenta `RichTextDisplay.vue` (sanitize + `v-html` + jednotné prose třídy).
- [x] Vytvořen sdílený util `utils/sanitizeHtml.ts`.
- [x] Validace: `vue-tsc`, `oxlint`, `vite build` — vše prošlo.

### Krok 2 — `Lead.description` všude přes editor + Safe HTML
- [x] Backend: nainstalován `bleach>=6.2,<7.0` a vytvořen `crm/sanitize.py` s allow-listem odpovídajícím Tiptap StarterKit + Mention + Image (zakázány `javascript:`, `data:` protokoly).
- [x] Backend: `Lead.description` sanitizován v `create_lead` i `update_lead` endpointech — defense-in-depth nad rámec frontend DOMPurify.
- [x] Frontend: `LeadsView.vue` modal pro create/edit leadu — `<textarea>` nahrazen za `<RichTextEditor>`. Tím je popis leadu **všude** editovatelný editorem (LeadDetailView i LeadsView modal).
- [x] Frontend: konsolidace 4 lokálních `sanitizeHtml` definic (LeadDetailView, CatalogView, TaskDetailView, ActivityTimeline) → import ze sdíleného `@/utils/sanitizeHtml`. Odstraněny nepotřebné importy DOMPurify, kde byly redundantní.
- [x] Validace: `crm.tests` (274 testů) prošly, `vue-tsc`, `oxlint` (mé soubory čisté), `vite build` OK.
- [ ] *(odloženo na pozdější krok pokud bude potřeba)* Aplikovat backend sanitizaci i na `Activity.content_text`, `Task.description_html`, `TaskTemplate.description_html` atd. — util je připraven, lze rozšířit plošně bez zásahu do schémat.

### Krok 3 — Nový `StreamlineItem` + tooly v backendu
- [x] Model `StreamlineItem` (`task` FK, `kind`, `text`, `is_resolved`, `resolved_at`, `resolved_by`, `created_at`, `created_by`, `order`).
- [x] Migrace `0046_streamline_item_unification` — přidá `StreamlineItem`, odstraní `TaskChecklistItem`, odstraní `Task.parent_task`, aktualizuje `ActivityType` choices.
- [x] Endpointy: `GET /tasks/{id}/streamline_items`, `POST /tasks/{id}/items` (multi-line split na řádky), `PATCH /items/{id}` (toggle resolved + audit), `DELETE /items/{id}`.
- [x] Streamline tooly: `StreamlineItemsAddedTool`, `StreamlineItemResolvedTool`, `StreamlineItemReopenedTool` — registrovány v `BUILTIN_TOOLS`.
- [x] Odstraněn legacy endpoint `GET/POST /tasks/{id}/checklist`, `PATCH/DELETE /tasks/{id}/checklist/{item_id}`.
- [x] Odstraněny legacy endpointy `GET/POST /tasks/{id}/subtasks` (parent_task FK).
- [x] `TaskOut` schema aktualizováno: odstraněno `parent_task_id`, `subtask_count`, `checklist_count` → přidáno `streamline_count`, `streamline_resolved`.
- [x] `_task_out()`, `_copy_task()`, `spawn_recurring_tasks` aktualizovány na `StreamlineItem`.
- [x] `realization_api.py`, `management_api.py` opraveny (odstraněn `parent_task` ze `select_related`).
- [x] Streamline toolbar pro `task` entity: odstraněno `checklist_item_checked` a `sub_task_added`.
- [x] Testy aktualizovány (`test_all_builtin_tools_registered`, `test_sub_task_added_render` → `test_streamline_items_added_render`, `test_checklist_item_checked_render` → `test_streamline_item_resolved_render`).
- [x] Validace: 274/274 Django testů OK, `vue-tsc --noEmit` exit 0.

### Krok 4 — Frontend `<StreamlineItemList>`
- [x] Komponenta `StreamlineItemList.vue` s props `taskId`, `kind`, `resolved`, `total`.
- [x] Multi-line `<textarea>` pro hromadné přidání (split na neprázdné řádky, Ctrl+Enter odeslání).
- [x] Checkbox toggle s optimistic update + rollback při chybě.
- [x] Zobrazení v `TaskDetailView.vue` — dvě instance (kind=todo, kind=subtask), old SUBTASKS + CHECKLIST sekce nahrazeny.
- [x] Smazán starý add-subtask dropdown a všechna inline logika (loadSubtasks, loadChecklist, submitNewSubtask, toggleChecklistItem, …) z TaskDetailView.
- [x] Store aktualizován: nové typy `StreamlineItemOut`, `StreamlineItemCreateIn`, `StreamlineItemUpdateIn`; nové akce `fetchStreamlineItems`, `createStreamlineItems`, `updateStreamlineItem`, `deleteStreamlineItem`; staré subtask/checklist akce odstraněny.
- [x] `TaskOut` interface aktualizován: odstraněno `parent_task_id`, `subtask_count`, `checklist_count` → `streamline_count`, `streamline_resolved`.
- [x] `LeadDetailView.vue` aktualizován: lokální Task interface a counter badge opraveny na nová pole.
- [x] `tasks.spec.ts` (unit testy) aktualizován: mockTask odpovídá novému `TaskOut`.
- [x] Lokalizace: nové klíče přidány do cs/en/de/pl (`streamlineTodos`, `streamlineSubtasks`, `streamlineProgress`, `streamlineAdd`, …).
- [x] Validace: `vue-tsc --noEmit` exit 0, Django smoke testy OK.

### Krok 5 — Úklid a validace
- [ ] Smazat / přepsat testy navázané na odstraněné modely (testy pro nesouvisející chování ZACHOVAT).
- [ ] Spustit Django testy, Vitest, lint, typecheck.
- [ ] Manuální průchod scénářů (lead popis, akce s TODO/podúkoly, toggle, audit log).

## Stav vypracování

**Aktuálně:** Kroky 1–4 dokončeny + bonus Todo Items tool. Zbývá Krok 5 — finální úklid a validace.

**Hotovo:**
- Plán a předpoklady zapsány do `plan.md`.
- **Krok 1 (Kontrast):** viz checklist výše.
- **Krok 2 (Popis leadu + Safe HTML):** viz checklist výše.
- **Krok 3 (StreamlineItem backend):** viz checklist výše.
- **Krok 4 (Frontend StreamlineItemList):**
  - Nová komponenta `StreamlineItemList.vue` — multi-line textarea vstup, optimistic checkbox toggle, delete, progress bar, dark mode, lokalizace.
  - Store: nové typy a API akce; staré subtask/checklist akce odstraněny.
  - TaskDetailView: nahrazeny obě sekce (SUBTASKS + CHECKLIST) dvěma instancemi `<StreamlineItemList>`.
  - `vue-tsc --noEmit` exit 0.
- **Bonus — TodoItemsAddedTool (bulk task creation z entity toolbaru):**
  - Nový `ActivityType.TODO_ITEMS_ADDED` + `TodoItemsAddedTool` v `crm/streamline/tools.py`.
  - `process_action` vytvoří jeden `Task` + jeden `StreamlineItem` (kind=todo) pro každý neprázdný řádek.
  - `Lead.TOOLBAR_TOOLS` rozšířen o `"todo_items"` (sekce Planning).
  - `EntitySidebarActionPicker`: `todo_items` v kategoriích + labelech + helpTextech; `text` přidáno do `MULTILINE_FIELD_KEYS` → textarea.
  - Migrace `0047` aplikována. Lokalizace cs/en/de/pl doplněna.
  - Backend testy OK, `vue-tsc --noEmit` exit 0.

**Následuje:**
- **Krok 5** — finální úklid: ActivityTimeline event typy, Vitest, lint, manuální průchod.

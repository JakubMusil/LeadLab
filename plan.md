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
- [ ] Audit všech míst, kde se zobrazuje výstup z `RichTextEditor` (search `prose ` ve `frontend-spa/src/`).
- [ ] V `RichTextEditor.vue` (edit oblast): nastavit explicitní `text-gray-900 dark:text-gray-100` na editor content; zkontrolovat placeholder, mention chip, list markery, inline kód.
- [ ] Doplnit chybějící `dark:prose-invert` a sjednotit kontejnerový `text-gray-700 dark:text-gray-300` na všech read-only místech (známý hot-spot: `LeadDetailView.vue:564`).
- [ ] Vytvořit shared komponentu `RichTextDisplay.vue` (sanitize + `v-html` + jednotné prose třídy), použít ji všude místo ad-hoc `v-html`.
- [ ] Spustit lint + typecheck.

### Krok 2 — `Lead.description` všude přes editor + Safe HTML
- [ ] Backend: přidat HTML pole na Lead (buď `description_html`, nebo přepnout `description` na HTML s server-side sanitizací — finální rozhodnutí v rámci kroku).
- [ ] Backend: sjednotit sanitizaci (utility v `crm/`), aplikovat na all writes.
- [ ] Schémata `LeadOut`/`LeadIn`/`LeadUpdateIn` upravit.
- [ ] Frontend: najít všechna místa, kde se popis leadu zobrazuje (sidebar, kartičky, tooltipy, public/share view, exporty, notifikace) a sjednotit přes `RichTextDisplay`. Edit vždy přes `RichTextEditor`.
- [ ] ESLint pravidlo `vue/no-v-html` (s povolenou výjimkou pro `RichTextDisplay`) — pokud nezvyšuje šum.
- [ ] Migrace dat: stávající plain-text → `<p>` (nikoliv mazání).

### Krok 3 — Nový `StreamlineItem` + tooly v backendu
- [ ] Model `StreamlineItem` (`task` FK, `kind`, `text`, `is_resolved`, `resolved_at`, `resolved_by`, `created_at`, `created_by`, `order`).
- [ ] Migrace, která přidá nový model a ODSTRANÍ legacy `TaskChecklistItem` + `Task.parent_task` (bez převodu dat — explicitně dle požadavku).
- [ ] Endpointy: `POST /tasks/{id}/items` (multi-line split na řádky), `PATCH /items/{id}` (toggle resolved), `DELETE /items/{id}`.
- [ ] Streamline tooly: `StreamlineItemsAddedTool`, `StreamlineItemResolvedTool`, `StreamlineItemReopenedTool` (nebo jeden tool s metadata.action).
- [ ] Registrace v `BUILTIN_TOOLS`.

### Krok 4 — Frontend `<StreamlineItemList>`
- [ ] Komponenta `StreamlineItemList.vue` s prop `kind` a `taskId`.
- [ ] Multi-line `<textarea>` pro hromadné přidání (split na neprázdné řádky).
- [ ] Checkbox toggle s optimistic update.
- [ ] Zobrazení v `TaskDetailView.vue` (a kdekoli dalšího, kde dnes je checklist/subtasks).
- [ ] Smazat staré komponenty/store sekce pro `checklist` a `subtasks`.
- [ ] Lokalizace cs/en.

### Krok 5 — Úklid a validace
- [ ] Smazat / přepsat testy navázané na odstraněné modely (testy pro nesouvisející chování ZACHOVAT).
- [ ] Spustit Django testy, Vitest, lint, typecheck.
- [ ] Manuální průchod scénářů (lead popis, akce s TODO/podúkoly, toggle, audit log).

## Stav vypracování

**Aktuálně:** Plán uložen, začínám Krok 1.

**Hotovo:**
- Plán a předpoklady zapsány do `plan.md`.

**Následuje:**
- Krok 1 — kontrastní fix napříč editorem a všemi read-only renderery výstupu z editoru.

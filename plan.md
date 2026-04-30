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

**Aktuálně:** Krok 1 dokončen, pokračuji Krokem 2.

**Hotovo:**
- Plán a předpoklady zapsány do `plan.md`.
- **Krok 1 (Kontrast):**
  - Identifikováno, že `@tailwindcss/typography` plugin nebyl nainstalovaný — proto třídy `prose`/`dark:prose-invert` napříč SPA neaplikovaly žádné styly. To je kořenová příčina kontrastních problémů.
  - Přidán `@tailwindcss/typography@^0.5.19` jako devDependency (bez známých CVE).
  - V `tailwind.config.ts` zaregistrován plugin a customizována paleta `prose` proměnných pro WCAG-AA kontrast jak v light, tak v dark mode.
  - V `RichTextEditor.vue` doplněna explicitní `text-gray-900 dark:text-gray-100` na editovací oblast a ztmaven placeholder z `gray-400` (~3.4:1) na `gray-500` (~4.8:1) v light mode, s parem `gray-400` v dark mode.
  - Opraven hot-spot `LeadDetailView.vue:564` (popis úkolu): `text-gray-500` → `text-gray-700 dark:text-gray-300` + doplněno `dark:prose-invert`.
  - Vytvořen sdílený util `src/utils/sanitizeHtml.ts` (single source of truth pro DOMPurify sanitizaci) — připraveno k postupné konsolidaci 4 lokálních duplicit.
  - Vytvořena sdílená komponenta `src/components/RichTextDisplay.vue` pro jednotné read-only renderování HTML z editoru.
  - Validace: `vue-tsc --build`, `oxlint`, `vite build` — vše čisté.

**Následuje:**
- Krok 2 — `Lead.description` všude přes editor + Safe HTML rendering (backend HTML pole + sanitizace, sjednocení všech zobrazení popisu leadu na `RichTextEditor` / `RichTextDisplay`).
- V rámci Kroku 2 také postupně nahradit lokální `sanitizeHtml` definice v `LeadDetailView.vue`, `CatalogView.vue`, `TaskDetailView.vue` a `ActivityTimeline.vue` importem ze sdíleného utilu.

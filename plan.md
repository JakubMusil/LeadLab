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

**Aktuálně:** Kroky 1 a 2 dokončeny. Čekám na potvrzení/úpravu předpokladů uživatelem před začátkem Kroku 3 (smazání legacy modelů bez migrace dat je nevratná operace — chci si být jistý zadáním).

**Hotovo:**
- Plán a předpoklady zapsány do `plan.md`.
- **Krok 1 (Kontrast):** viz checklist výše. Plugin Tailwind Typography registrovaný s WCAG-AA paletou; placeholder editor a popis úkolu opraveny; `RichTextDisplay` + sdílený `sanitizeHtml` util pro plošné konzistentní renderování.
- **Krok 2 (Popis leadu + Safe HTML):**
  - Backend `crm/sanitize.py` s bleach allow-listem.
  - `Lead.description` sanitizace v create + update endpointech.
  - `LeadsView.vue` modal — editor místo textarea (popis leadu nyní editovatelný přes editor i v modalu).
  - 4× konsolidace lokálních `sanitizeHtml` na sdílený util.
  - Backend testy 274/274 OK, frontend build + typecheck OK, lint na změněných souborech čistý.

**Následuje:**
- **Krok 3** — Nový `StreamlineItem` model + tooly + smazání legacy `TaskChecklistItem` a `Task.parent_task` bez data migrace. Před začátkem chci ideálně potvrzení od uživatele (bod níže), ale pokud nepřijde, budu pokračovat podle zapsaných pracovních předpokladů.

**Otevřené body pro uživatele (viz "Pracovní předpoklady" výše):**
1. Potvrzení že "akce" = `Task` (ano/ne).
2. Položky bez assignee/deadline (jen text + resolved) — souhlas?
3. Při hromadném vstupu — jeden agregovaný streamline záznam ("přidáno N položek") + N záznamů při toggle. Souhlas?
4. Potvrzení že `Lead.description` plain-text data zůstanou tak, jak jsou (sanitizace plain text propustí beze změny — žádná data migrace nutná).

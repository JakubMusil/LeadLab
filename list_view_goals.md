# Cíle: Vylepšení výpisu /app/opportunities (a dalších výpisů)

## Kontext

Stránka `/app/opportunities` (mapuje na `LeadsView.vue`) zobrazuje tabulku / seznam / kanban příležitostí.

---

## Celkové cíle

### A. Avatary a uživatelé v řádcích (tabulka + seznam)
- Zobrazit avatar tvůrce příležitosti vždy
- Zobrazit avatar řešitele (assigned_to) pouze pokud se liší od tvůrce
- Avatar = komponenta `Avatar.vue` (velikost `xs`), s inicálami nebo foto

### B. Defaultní pohled = seznam (ne tabulka)
- Při prvním načtení (bez uloženého preferencí) zobrazit seznam
- Stávající localStorage klíč `leadlab_leads_displaymode_u{userId}` zachovat

### C. Řazení tabulky (kliknutí na záhlaví sloupce)
- Sloupce: název, stav, zdroj, hodnota, skóre, tvůrce, řešitel, datum
- Směr: ASC / DESC
- Vizuální indikátor (šipka) v záhlaví
- Řazení probíhá na frontendu (klientsky) nad načtenými daty

### D. Pokročilá filtrace
- Stávající: status, source
- Přidat: assigned_to (řešitel), created_by (tvůrce), hodnotový rozsah (min/max), datum vytvoření (od/do)
- Filtrace posílá parametry na API (server-side) nebo filtruje lokálně

### E. Uživatelsky ukládané pohledy (Saved Views)
- Stávající `SavedView` ukládá jen status + source
- Rozšířit o: sort_by, sort_dir, všechny aktivní filtry, výběr viditelných sloupců, pořadí sloupců
- Pohled se načte kliknutím na záložku (bookmark) v hlavičce
- Pohled lze přejmenovat, smazat

### F. Výběr a pořadí sloupců
- Uživatel si může zapnout/vypnout sloupce (skóre, tvůrce, řešitel, hodnota, atd.)
- Výběr se ukládá do SavedView nebo do localStorage
- Drag & drop pořadí sloupců (bonus)

### G. Systematická znovupoužitelnost
- Vytvořit `composable useListView(entity, columns, defaultFilters)` který zapouzdří:
  - filter state, sort state, columns config
  - načtení a uložení pohledu
  - localStorage persistence
- Nová komponenta `ListViewTable.vue` (generická tabulka se sorting/grouping)
- Použít pro: Realizace (`/app/realizations`), Správu (`/app/management`), případně Adresář

---

## Plán relací

### Relace 1 – Avatary + defaultní pohled (TATO RELACE)
**Cíl**: Zobrazit avatary v tabulce i seznamu, nastavit default na 'list'

**Kroky:**
1. **Backend** (`crm/api.py`):
   - Přidat `assigned_to_name: Optional[str]` do `LeadOut` Pydantic schématu
   - Přidat výpočet `assigned_to_name` do funkce `_lead_out()`
   - Přidat `select_related('assigned_to')` do dotazu v `list_leads()`
2. **Frontend – store** (`stores/leads.ts`):
   - Přidat `assigned_to_name: string | null` do TypeScript interface `LeadOut`
3. **Frontend – view** (`views/LeadsView.vue`):
   - Změnit výchozí `viewMode` z `'table'` na `'list'`
   - Import `Avatar` komponenty
   - V TABLE VIEW: přidat sloupec "Uživatelé" nebo vložit mini-avatary vedle názvu
   - V LIST VIEW: přidat mini-avatary napravo (mezi hodnotu a akce)

### Relace 2 – Řazení tabulky + pokročilé filtry
**Cíl**: Tabulka s klikacím řazením, rozšířené filtry

**Kroky:**
1. Přidat sort state (`sortField`, `sortDir`) do LeadsView
2. Sortable table headers (šipky) – inline v LeadsView nebo extrahovat do `OpportunityTableView.vue`
3. Přidat filtry: assigned_to (dropdown z členů firmy), hodnota min/max, datum od/do
4. Backend: přidat `sort_by`, `sort_dir`, `value_min`, `value_max`, `created_after`, `created_before` parametry do `list_leads()`
5. Store: rozšířit `LeadFilters` o nové parametry

### Relace 3 – Výběr sloupců + rozšíření SavedViews
**Cíl**: Uložit sort + sloupce do SavedView

**Kroky:**
1. Rozšířit `SavedView` model/schema o `columns: list[str]`, `sort_by`, `sort_dir`, více filter polí
2. UI pro výběr sloupců (checkbox dropdown v záhlaví tabulky)
3. Uložit/načíst columns výběr do/z SavedView nebo localStorage
4. Obnovit celý pohled (filtry + sort + sloupce) z uložené záložky

### Relace 4 – Generická znovupoužitelná vrstva
**Cíl**: Composable + generická tabulka pro budoucí použití

**Kroky:**
1. Vytvořit `composables/useListView.ts` s logikou filter/sort/columns
2. Vytvořit `components/SmartListTable.vue` (generická tabulka, přijímá column definitions)
3. Refaktorovat LeadsView na `useListView`
4. Aplikovat na RealizationsView (pilotní druhé použití)

---

## Průběh implementace

### Relace 1 – DOKONČENA (2026-05-03)

**Hotovo:**
- [x] Plán zapsán do `list_view_goals.md`
- [x] Backend: `assigned_to_name` přidáno do `LeadOut` schema a `_lead_out()`, `select_related('assigned_to')` přidáno do listovacího dotazu
- [x] Frontend store: `assigned_to_name: string | null` přidáno do TypeScript interface `LeadOut`
- [x] Frontend view: výchozí `viewMode` změněn z `'table'` na `'list'`
- [x] Frontend view: Avatar importován, zobrazen v tabulce i seznamu (tvůrce vždy, řešitel pokud se liší)

### Relace 2 – DOKONČENA (2026-05-03)

**Hotovo:**
- [x] Backend: přidány parametry `created_by`, `value_min`, `value_max`, `sort_by`, `sort_dir` do `list_leads()`
- [x] Backend: DB-level řazení (title, status, source, value, created_at, updated_at) s ochranou allowlistu
- [x] Store: `LeadFilters` rozšířen o `created_by`, `value_min`, `value_max`, `created_after`, `created_before`, `sort_by`, `sort_dir`
- [x] Store: `fetchLeads()` předává nové parametry na API
- [x] Frontend: načítání členů firmy (`loadMembers`) pro filtrovací dropdowny
- [x] Frontend: sort state (`sortField`, `sortDir`, `sortedLeads` computed) – klientské řazení na aktuální stránce
- [x] Frontend: klikatelná záhlaví tabulky s šipkami (title, status, source, value, created_at)
- [x] Frontend: collapsible panel pokročilých filtrů (řešitel, tvůrce, hodnota min/max, datum od/do)
- [x] Frontend: `loadLeads(page)` helper konsoliduje všechny filtrační parametry
- [x] Frontend: pagination přepojeno na `loadLeads(page)`
- [x] Frontend: SavedView ukládá a obnovuje pokročilé filtry
- [x] Locale: přidány klíče advancedFilters, filterAll, filterAssignedTo, filterCreatedBy, filterValueMin/Max, filterCreatedAfter/Before, clearFilters, saveViewDescription/Advanced do cs/en/de/pl

### Relace 3 – DOKONČENA (2026-05-03)

**Hotovo:**
- [x] Backend (`crm/models.py`): přidáno `columns = JSONField(default=list)` do `SavedView`
- [x] Migration `0058_savedview_columns.py`
- [x] Backend (`crm/api.py`): `columns: List[str]` přidáno do `SavedViewOut`, `SavedViewIn`, `_saved_view_out()`, `create_saved_view()`
- [x] Store (`savedViews.ts`): `columns: string[]` přidáno do obou TS interfaces
- [x] Frontend: definice `TABLE_COLUMNS` (6 sloupců, každý s `defaultVisible`)
- [x] Frontend: `visibleColumns` ref s localStorage persistencí per uživatel (klíč `leadlab_leads_cols_u{userId}`)
- [x] Frontend: `isColVisible()`, `toggleColumn()`, `resetColumns()` funkce
- [x] Frontend: column picker dropdown (AdjustmentsHorizontalIcon v záhlaví tabulky) – checkboxy, reset tlačítko, zavírá se kliknutím mimo
- [x] Frontend: tabulka (`<th>` + `<td>`) reaguje na `visibleColumns` přes `v-if` – bez responsivních hidden tříd
- [x] Frontend: `saveCurrentView()` ukládá `sort_by`, `sort_dir`, `columns`
- [x] Frontend: obnovení pohledu ze SavedView obnovuje sort + columns (s validací allowlistem)
- [x] Frontend: dialog uložení pohledu zobrazuje info o sortu a počtu sloupců
- [x] Locale: přidány klíče `colPicker`, `resetColumns`, `saveViewSort`, `saveViewColumns`, `sort_asc/desc`, `col_*` do cs/en/de/pl

**Co se dělá v příští relaci (Relace 4):**
- Composable `useListView(entity, columns, defaultFilters)` – zapouzdření filter/sort/columns/localStorage
- Generická `SmartListTable.vue` (přijímá column definitions, renderuje thead + tbody)
- Refaktorovat `LeadsView.vue` na `useListView`
- Aplikovat na `RealizationsView.vue` (pilotní druhé použití)

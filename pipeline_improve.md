# Pipeline Field Settings — Improvement Plan

## Cíl

Rozšířit `CategoryField` o konfiguraci **typu hodnoty**, **widgetu** a **validačních pravidel**,
aby bylo možné každému poli v pipeline nastavit:
- jaký datový typ uchovává (`value_type`)
- jaký UI input se použije ve formulářích (`widget`)
- pravidla pro hodnoty — rozsahy, výčet možností, regex (`validation_rules`)
- volitelný přepis popisku (`label_override`)
- nápovědu zobrazenou u inputu (`help_text`)

---

## Fáze

### Fáze 1 — Backend (model + API) ✅

#### 1a. Model `CategoryField` — nová pole
- `value_type` — CharField, choices, default `'text'`
  - Hodnoty: `text`, `number`, `currency`, `date`, `datetime`, `boolean`, `select`, `multiselect`, `url`, `email`
- `widget` — CharField, choices, default `'auto'`
  - Hodnoty: `auto`, `text_input`, `textarea`, `number_input`, `date_picker`, `datetime_picker`, `toggle`, `select`, `multiselect`, `color_picker`, `currency_input`, `rich_text`
- `validation_rules` — JSONField, blank/null, výchozí `{}`
  - Příklady klíčů: `min`, `max`, `pattern`, `options` (seznam pro select)
- `label_override` — CharField max 100, blank, výchozí `''`
- `help_text` — CharField max 255, blank, výchozí `''`

#### 1b. Migrace
- `crm/migrations/0005_categoryfield_extended.py`

#### 1c. API schémata (`pipeline_config_api.py`)
- Rozšířit `CategoryFieldOut`, `CategoryFieldIn`, `CategoryFieldUpdateIn`
- Rozšířit `_field_out()` helper
- Přidat serverovou validaci: pokud `widget` je `select`/`multiselect`, `validation_rules.options` musí být neprázdný seznam

**Status: ✅ Hotovo**

---

### Fáze 2 — Frontend (store + UI + i18n) ✅

#### 2a. Store (`frontend-spa/src/stores/pipeline.ts`)
- Rozšířit `CategoryFieldOut` a `CategoryFieldIn` interface o nová pole

#### 2b. UI (`frontend-spa/src/views/PipelineSettingsView.vue`)
- V edit formuláři pole přidat:
  - Dropdown **Typ hodnoty** (`value_type`)
  - Dropdown **Widget** (filtrovaný / reagující na value_type)
  - Sekce **Pravidla** — dynamicky dle value_type:
    - `number`/`currency`: min/max number inputs
    - `select`/`multiselect`: editovatelný tag-list možností (`options`)
    - `text`: volitelný regex `pattern`
  - Input **Popisek (přepis)** (`label_override`)
  - Input **Nápověda** (`help_text`)
- Zobrazit `label_override` / `value_type` badge v read-only řádku pole

#### 2c. i18n — všechny 4 locale soubory (cs, en, pl, de)
- Nové klíče pod `pipeline.field.*`

**Status: ✅ Hotovo**

---

### Fáze 3 — Seed command ✅

- Aktualizovat `crm/management/commands/seed_pipeline_categories.py`
- Přidat rozumné výchozí `value_type` pro každý `FIELD_KEY_CHOICES`:
  - `value_currency` → `value_type: currency`, `widget: currency_input`, `help_text_override`
  - `date_range` → `value_type: date`, `widget: date_picker`, `help_text_override`
  - `expires_at` → `value_type: date`, `widget: date_picker`, `help_text_override`
  - `notes` → `value_type: text`, `widget: textarea`, `help_text_override`
  - `source` → `value_type: select`, `widget: select`, `validation_rules.options`, `help_text_override`
  - `origin_record` → `value_type: text`, `widget: text_input`, `help_text_override`

**Status: ✅ Hotovo**

---

### Fáze 4 — Pipeline Fields panel v RecordDetailView ✅

- Přidat panel "Pipeline Fields" v pravém sidebaru RecordDetailView
- Panel se zobrazí pouze pokud má záznam kategorii s viditelnými poli
- Pole `value_currency` a `source` se v panelu nezobrazují (jsou v hlavní sekci)
- Každé pole zobrazí:
  - Label (label_override nebo přeložený field_key)
  - Aktuální hodnotu z PipelineRecord
  - Tlačítko Upravit (zobrazí se při hoveru)
- Inline editing pro každý field_key:
  - `expires_at` → date input
  - `date_range` → dva date inputy (Od / Do)
  - `notes` → textarea
- i18n klíče: `pipeline.fieldEdit`, `fieldSaved`, `fieldSaveFailed`, `fieldSaving`, `fieldSaveBtn`, `fieldStartDate`, `fieldEndDate` — přidány do všech 4 locale souborů

**Status: ✅ Hotovo**

---

### Fáze 5 — Runtime validace hodnot polí ✅

- Při ukládání hodnoty přes API ověřit `validation_rules` daného `CategoryField`
  - `min`/`max` pro number/currency
  - `pattern` (regex) pro text
  - `options` pro select/multiselect — hodnota musí být v seznamu
- Frontend: zobrazit chybové zprávy při neplatné hodnotě (inline pod inputem, ne jen toast)

**Status: ✅ Hotovo**

---

### Fáze 6 — Kanban karta s hodnotami polí ✅

- Zobrazit klíčová pole kategorie (maximálně 2) přímo na Kanban kartě v RecordsView
- Ušetří přechod do detailu záznamu pro rychlé informace

**Status: ✅ Hotovo**

---

### Fáze 7 — Drag-and-drop pro stage-based Kanban ✅

- Přidána metoda `patchStage(id, stageId)` do records store — optimistický update s rollbackem
- Stage-based Kanban v RecordsView získal drag-and-drop:
  - Karty mají `draggable="true"` a `@dragstart` handler
  - Sloupce reagují na `@dragover`, `@dragleave`, `@drop`
  - Vizuální indikace: modrý highlight + ring na cílovém sloupci při tahu
  - Prázdný sloupec zobrazuje "Drop here" místo "No records in this stage"
- Nové refs/funkce: `draggingStageRecord`, `dragOverStageId`, `onStageDragStart`, `onStageDragOver`, `onStageDragLeave`, `onStageDrop`

**Status: ✅ Hotovo**

---

### Fáze 8 — Dialog při přesunu do terminální stage ✅

- Při přetažení Kanban karty na terminální stage (is_terminal=true) se zobrazí potvrzovací modal:
  - Název záznamu + cílová stage (barevný badge)
  - Volitelné textové pole pro poznámku k výsledku
  - Checkbox „Vytvořit kontrolní bod" + vstup pro název a datum
  - Tlačítko Potvrdit (zelené „Označit jako Vyhráno ✓" pro is_won, jinak šedé „Potvrdit přesun")
  - Tlačítko Zrušit
- Na potvrzení: volání `patchStage`, pokud je zaškrtnuto, také POST nový checkpoint
- i18n klíče: `terminalMoveTitle`, `terminalMoveSubtitle`, `terminalMoveNote`, `terminalMoveNotePlaceholder`, `terminalAddCheckpoint`, `terminalCheckpointName`, `terminalCheckpointNamePlaceholder`, `terminalCheckpointDate`, `terminalConfirmWon`, `terminalConfirmLost`, `terminalMoveFailed`, `terminalCheckpointFailed` — přidány do všech 4 locale souborů

**Status: ✅ Hotovo**

---

## Co bylo uděláno (log)

### Relace 1
- Vytvořen tento soubor s plánem
- **Fáze 1 dokončena**: model (`value_type`, `widget`, `validation_rules`, `label_override`, `help_text_override`), migrace 0005, API schémata + serverová validace pro select/multiselect
- **Fáze 2 dokončena**: store types, rozšířený UI formulář (edit + nový field) s dropdowny, min/max, options textarea, label override, help text; i18n klíče (cs, en, pl, de)

### Relace 2
- **Fáze 3 dokončena**: seed command aktualizován — každý FIELD_KEY_CHOICES má nyní `value_type`, `widget`, `validation_rules` (pro source) a `help_text_override`
- **Fáze 4 dokončena**: přidán panel "Pipeline Fields" v RecordDetailView sidebaru — zobrazuje viditelná pole kategorie s hodnotami a inline editací (date_range, expires_at, notes); nové i18n klíče do všech 4 locale souborů

### Relace 3
- **Fáze 5 dokončena**: backend helper `_validate_record_field_rules` v `crm/api.py` — validuje `value` (min/max), `notes` (pattern regex), `source` (options) oproti `CategoryField.validation_rules`; frontend zobrazí chybu inline pod editačním inputem (ref `fieldEditError`)
- **Fáze 6 dokončena**: stage-based Kanban karta v RecordsView zobrazuje až 2 viditelná pole kategorie (date_range, notes, origin_record) pod hodnotou/datem expirace; pomocná funkce `getKanbanCardFields(record)` v RecordsView.vue

### Relace 4
- **Fáze 7 dokončena**: přidán drag-and-drop pro stage-based Kanban — `patchStage` v records store, drag handlery v RecordsView, vizuální feedback (modrý highlight sloupce)

### Relace 5
- **Fáze 8 dokončena**: při přetažení Kanban karty do terminální stage se zobrazí potvrzovací modal (`Modal` + `Button` komponenty); modal nabízí volitelnou poznámku k výsledku a možnost vytvořit checkpoint (s názvem a datem); tlačítko potvrzení je zelené pro stage `is_won`, jinak standardní; i18n klíče přidány do všech 4 locale souborů (cs/en/pl/de)

### Příště
- Žádné další fáze naplánované — pipeline_improve.md je kompletní
- Možná rozšíření: filtrování Kanban karet dle pole kategorie; bulk-move záznamů mezi stages

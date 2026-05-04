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

### Fáze 5 — Runtime validace hodnot polí ⬜

- Při ukládání hodnoty přes API ověřit `validation_rules` daného `CategoryField`
  - `min`/`max` pro number/currency
  - `pattern` (regex) pro text
  - `options` pro select/multiselect — hodnota musí být v seznamu
- Frontend: zobrazit chybové zprávy při neplatné hodnotě

**Status: ⬜ Bude příště**

---

### Fáze 6 — Kanban karta s hodnotami polí ⬜

- Zobrazit klíčová pole kategorie (maximálně 2-3) přímo na Kanban kartě v RecordsView
- Ušetří přechod do detailu záznamu pro rychlé informace

**Status: ⬜ Bude příště**

---

## Co bylo uděláno (log)

### Relace 1
- Vytvořen tento soubor s plánem
- **Fáze 1 dokončena**: model (`value_type`, `widget`, `validation_rules`, `label_override`, `help_text_override`), migrace 0005, API schémata + serverová validace pro select/multiselect
- **Fáze 2 dokončena**: store types, rozšířený UI formulář (edit + nový field) s dropdowny, min/max, options textarea, label override, help text; i18n klíče (cs, en, pl, de)

### Relace 2
- **Fáze 3 dokončena**: seed command aktualizován — každý FIELD_KEY_CHOICES má nyní `value_type`, `widget`, `validation_rules` (pro source) a `help_text_override`
- **Fáze 4 dokončena**: přidán panel "Pipeline Fields" v RecordDetailView sidebaru — zobrazuje viditelná pole kategorie s hodnotami a inline editací (date_range, expires_at, notes); nové i18n klíče do všech 4 locale souborů

### Příště
- Fáze 5: Runtime validace hodnot polí dle `validation_rules`
- Fáze 6: Zobrazení klíčových polí kategorie na Kanban kartě

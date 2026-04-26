# Contributing a New Locale

Thank you for helping make LeadLab accessible to more users! This guide walks you through adding a new UI language to the frontend SPA.

## Overview

All UI strings live in JSON files under `frontend-spa/src/locales/`. The English file (`en.json`) is the **reference locale** — every key present there must also exist in every other locale file. A CI check enforces this automatically.

---

## Step-by-step guide

### 1. Copy the reference locale

```bash
cp frontend-spa/src/locales/en.json frontend-spa/src/locales/<lang>.json
```

Replace `<lang>` with the [BCP 47 language subtag](https://www.iana.org/assignments/language-subtag-registry/language-subtag-registry) for your language (e.g. `fr` for French, `es` for Spanish, `pt` for Portuguese).

### 2. Translate all values

Open `frontend-spa/src/locales/<lang>.json` and replace every English value with the correct translation. **Do not change the keys** — only translate the string values.

Example (French):
```json
{
  "nav": {
    "overview": "Vue d'ensemble",
    "leads": "Prospects",
    ...
  }
}
```

A few values contain interpolation placeholders such as `{rate}` or `{count}`. Keep those placeholders exactly as-is — only translate the surrounding text.

### 3. Register the locale in the app

**a. Import the new locale in `frontend-spa/src/main.ts`:**

```ts
import fr from './locales/fr.json'
```

**b. Add it to the `messages` map:**

```ts
const i18n = createI18n({
  legacy: false,
  locale: detectLocale(),
  fallbackLocale: 'en',
  messages: { en, cs, de, pl, fr },   // ← add fr here
})
```

**c. Update `detectLocale()` in `frontend-spa/src/composables/useI18n.ts`:**

```ts
return ['en', 'cs', 'de', 'pl', 'fr'].includes(browser) ? browser : 'en'
```

**d. Add the language button in `frontend-spa/src/views/SettingsView.vue`:**

Find the `v-for` that renders language buttons and add your locale:

```ts
v-for="lang in [
  { code: 'en', label: '🇬🇧 English' },
  { code: 'cs', label: '🇨🇿 Čeština' },
  { code: 'de', label: '🇩🇪 Deutsch' },
  { code: 'pl', label: '🇵🇱 Polski' },
  { code: 'fr', label: '🇫🇷 Français' },   // ← add your locale here
]"
```

**e. Add translated language name keys in every existing locale file:**

Each locale file has a `settings.english`, `settings.czech`, etc. key so users can see language names in their own language. Add a key for your new language in all locale files (including `en.json`, `cs.json`, `de.json`, and `pl.json`):

```json
// en.json
"french": "French"

// cs.json
"french": "Francouzština"

// de.json
"french": "Französisch"

// pl.json
"french": "Francuski"

// fr.json  (your new file)
"french": "Français"
```

### 4. Verify coverage locally

Run the locale coverage check before opening a pull request:

```bash
cd frontend-spa
node scripts/check-locales.mjs
```

The script prints a ✅ for each complete locale and an ❌ with a list of missing keys for any incomplete one. Fix all reported issues before proceeding.

### 5. Open a pull request

- Branch name: `i18n/<lang>-translations` (e.g. `i18n/fr-translations`)
- PR title: `i18n: add French (fr) translations`
- Describe any translation choices or terms you were unsure about in the PR description so reviewers can give feedback.

---

## Quality guidelines

| Guideline | Details |
|---|---|
| **Completeness** | Every key in `en.json` must be translated. The CI check will fail otherwise. |
| **Accuracy** | Prefer natural, idiomatic phrasing over literal word-for-word translation. |
| **Placeholders** | Keep `{rate}`, `{count}`, `{value}`, etc. exactly as they appear — they are replaced at runtime. |
| **Emoji** | Emoji in values (e.g. `📤 Send`) may be kept or adapted to local convention. |
| **Formality** | Match the formality level of the existing locales (informal/friendly where appropriate). |

---

## Running the CI check locally

```bash
cd frontend-spa
node scripts/check-locales.mjs
```

This is the same script that runs in GitHub Actions on every push and pull request.

---

## Questions?

Open an issue with the label **`i18n`** and we will be happy to help.

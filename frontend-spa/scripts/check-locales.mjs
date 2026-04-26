#!/usr/bin/env node
/**
 * Locale coverage check — fails if any key present in en.json is missing
 * from any other locale file in src/locales/.
 *
 * Usage: node scripts/check-locales.mjs
 *
 * The script exits with code 1 and prints all missing keys when coverage is
 * incomplete so that CI can catch regressions early.
 */

import { readFileSync, readdirSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const localesDir = join(__dirname, '..', 'src', 'locales')

/**
 * Recursively collect all dotted key paths from a nested object.
 * E.g. { a: { b: 'c' } } → ['a.b']
 */
function collectKeys(obj, prefix = '') {
  const keys = []
  for (const [k, v] of Object.entries(obj)) {
    const path = prefix ? `${prefix}.${k}` : k
    if (v !== null && typeof v === 'object' && !Array.isArray(v)) {
      keys.push(...collectKeys(v, path))
    } else {
      keys.push(path)
    }
  }
  return keys
}

const files = readdirSync(localesDir).filter((f) => f.endsWith('.json'))
const referenceFile = 'en.json'

if (!files.includes(referenceFile)) {
  console.error(`Reference locale file "${referenceFile}" not found in ${localesDir}`)
  process.exit(1)
}

const reference = JSON.parse(readFileSync(join(localesDir, referenceFile), 'utf8'))
const referenceKeys = collectKeys(reference)

let hasErrors = false

for (const file of files) {
  if (file === referenceFile) continue

  const locale = file.replace('.json', '')
  const data = JSON.parse(readFileSync(join(localesDir, file), 'utf8'))
  const localeKeys = new Set(collectKeys(data))

  const missing = referenceKeys.filter((k) => !localeKeys.has(k))

  if (missing.length > 0) {
    hasErrors = true
    console.error(`\n❌  Locale "${locale}" is missing ${missing.length} key(s):`)
    missing.forEach((k) => console.error(`     • ${k}`))
  } else {
    console.log(`✅  Locale "${locale}" — all ${referenceKeys.length} keys present`)
  }
}

if (hasErrors) {
  console.error('\nLocale coverage check FAILED. Add the missing translations and try again.')
  process.exit(1)
} else {
  console.log('\nLocale coverage check passed.')
}

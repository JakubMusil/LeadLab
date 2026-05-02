import DOMPurify from 'dompurify'

/**
 * Sanitize a string of HTML using DOMPurify with the default HTML profile.
 *
 * This is the single source of truth for HTML sanitization in the SPA. Any
 * place that renders rich-text content via `v-html` MUST first pass the value
 * through this function, or — preferably — use the `<RichTextDisplay>`
 * component which wraps this together with consistent typography classes.
 */

// Patterns stripped from style attribute values to block CSS injection.
// Covers: url(), expression() (old IE), and JS/VBScript pseudo-protocols.
const UNSAFE_STYLE_PATTERN = /url\s*\(|expression\s*\(|javascript\s*:|vbscript\s*:/gi

DOMPurify.addHook('uponSanitizeAttribute', (node, data) => {
  if (data.attrName === 'style') {
    // Strip dangerous CSS patterns from inline style values
    data.attrValue = data.attrValue.replace(UNSAFE_STYLE_PATTERN, '')
  }
})

export function sanitizeHtml(html: string | null | undefined): string {
  if (!html) return ''
  return DOMPurify.sanitize(html, {
    USE_PROFILES: { html: true },
    // Allow TipTap task-list attributes so checklist items render correctly
    // Allow style for text/background color (Color + Highlight extensions)
    // Allow link attributes for the Link extension
    // Allow colwidth for the Table extension
    ADD_ATTR: ['data-checked', 'data-type', 'style', 'target', 'rel', 'download', 'colwidth', 'data-colwidth'],
  })
}

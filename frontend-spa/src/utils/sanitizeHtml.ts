import DOMPurify from 'dompurify'

/**
 * Sanitize a string of HTML using DOMPurify with the default HTML profile.
 *
 * This is the single source of truth for HTML sanitization in the SPA. Any
 * place that renders rich-text content via `v-html` MUST first pass the value
 * through this function, or — preferably — use the `<RichTextDisplay>`
 * component which wraps this together with consistent typography classes.
 */
export function sanitizeHtml(html: string | null | undefined): string {
  if (!html) return ''
  return DOMPurify.sanitize(html, { USE_PROFILES: { html: true } })
}

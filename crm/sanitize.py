"""
HTML sanitization utilities for rich-text content.

Single source of truth on the backend for cleaning HTML produced by the
SPA's Tiptap-based ``RichTextEditor``. The frontend already sanitizes via
DOMPurify before rendering, but the backend sanitization layer is required
for defense-in-depth — there are renderers that bypass DOMPurify (email
notifications, push notifications, PDF/HTML exports, server-rendered
templates) and we must not store dangerous markup in the database.

The allow-list intentionally mirrors what Tiptap's StarterKit + Mention +
Image extensions can produce, so legitimate editor output passes through
unchanged.
"""

from __future__ import annotations

from typing import Optional

import bleach

# Tags emitted by Tiptap StarterKit (paragraph, headings, lists, blockquote,
# horizontal rule, code/preformatted, hard break, basic inline marks),
# plus image (Image extension) and span (Mention extension).
ALLOWED_TAGS: frozenset[str] = frozenset(
    {
        "a",
        "b",
        "blockquote",
        "br",
        "code",
        "em",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "hr",
        "i",
        "img",
        "li",
        "ol",
        "p",
        "pre",
        "s",
        "span",
        "strong",
        "u",
        "ul",
    }
)

ALLOWED_ATTRIBUTES: dict[str, list[str]] = {
    "a": ["href", "title", "target", "rel"],
    "img": ["src", "alt", "title", "width", "height"],
    # Mention chips carry data attributes from Tiptap's Mention extension.
    "span": ["class", "data-id", "data-label", "data-type"],
    "code": ["class"],
    "pre": ["class"],
}

# Only allow HTTP(S) and mailto links — explicitly rejects javascript:,
# data:, vbscript: and other vectors.
ALLOWED_PROTOCOLS: frozenset[str] = frozenset({"http", "https", "mailto"})


def sanitize_html(html: Optional[str]) -> str:
    """Sanitize an HTML string against the editor allow-list.

    Returns an empty string for ``None``/empty input. Strips disallowed
    tags entirely (rather than escaping them) so the stored content is
    safe to render via ``v-html`` / ``mark_safe`` in any renderer.
    """
    if not html:
        return ""
    return bleach.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
    )

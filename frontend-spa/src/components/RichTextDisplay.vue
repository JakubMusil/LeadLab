<script setup lang="ts">
/**
 * RichTextDisplay — read-only renderer for HTML produced by RichTextEditor.
 *
 * Always sanitizes input via the shared `sanitizeHtml` utility and applies
 * a consistent set of Tailwind Typography (`prose`) classes so contrast is
 * guaranteed in both light and dark mode.
 *
 * Use this component everywhere you need to display rich-text content
 * instead of inlining `v-html` and `prose` classes in each call-site.
 */
import { computed } from 'vue'
import { sanitizeHtml } from '@/utils/sanitizeHtml'

const props = withDefaults(
  defineProps<{
    /** Raw HTML produced by the editor. Will be sanitized before rendering. */
    html?: string | null
    /** Typography size: `xs`, `sm` (default) or `base`. */
    size?: 'xs' | 'sm' | 'base'
    /** Render `<div>` (block, default) or `<span>` (inline). */
    inline?: boolean
  }>(),
  {
    html: '',
    size: 'sm',
    inline: false,
  },
)

const tag = computed(() => (props.inline ? 'span' : 'div'))

const sizeClass = computed(() => {
  switch (props.size) {
    case 'xs':
      return 'prose-xs'
    case 'base':
      return 'prose-base'
    case 'sm':
    default:
      return 'prose-sm'
  }
})

const sanitized = computed(() => sanitizeHtml(props.html))
</script>

<template>
  <!-- eslint-disable-next-line vue/no-v-html -->
  <component
    :is="tag"
    class="prose dark:prose-invert max-w-none break-words text-gray-800 dark:text-gray-200"
    :class="sizeClass"
    v-html="sanitized"
  />
</template>

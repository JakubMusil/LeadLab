<script setup lang="ts">
/**
 * RichTextEditor — Tiptap-based rich-text editor for activity comments.
 *
 * Features:
 *  - Bold, italic, underline formatting
 *  - Ordered and bullet lists
 *  - Placeholder text
 *  - Exposes plain-text and HTML content via v-model (HTML)
 */
import { onBeforeUnmount, watch } from 'vue'
import { useEditor, EditorContent } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import Placeholder from '@tiptap/extension-placeholder'

const props = withDefaults(
  defineProps<{
    modelValue: string
    placeholder?: string
    disabled?: boolean
  }>(),
  {
    placeholder: 'Write a comment…',
    disabled: false,
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const editor = useEditor({
  content: props.modelValue,
  editable: !props.disabled,
  extensions: [
    StarterKit,
    Placeholder.configure({ placeholder: props.placeholder }),
  ],
  editorProps: {
    attributes: {
      class:
        'prose prose-sm dark:prose-invert max-w-none focus:outline-none min-h-[80px] px-3 py-2',
    },
  },
  onUpdate({ editor }) {
    emit('update:modelValue', editor.getHTML())
  },
})

watch(
  () => props.modelValue,
  (val) => {
    if (editor.value && editor.value.getHTML() !== val) {
      editor.value.commands.setContent(val, false, { preserveWhitespace: 'full' })
    }
  },
)

watch(
  () => props.disabled,
  (disabled) => {
    editor.value?.setEditable(!disabled)
  },
)

onBeforeUnmount(() => {
  editor.value?.destroy()
})
</script>

<template>
  <div
    class="border border-gray-300 dark:border-gray-600 rounded-lg overflow-hidden bg-white dark:bg-gray-900 focus-within:ring-2 focus-within:ring-[color:var(--brand-color)] focus-within:border-transparent transition-shadow"
    :class="{ 'opacity-60 cursor-not-allowed': disabled }"
  >
    <!-- Toolbar -->
    <div
      v-if="editor"
      class="flex items-center gap-0.5 px-2 py-1 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800"
    >
      <button
        type="button"
        class="p-1 rounded text-xs font-bold w-6 h-6 flex items-center justify-center transition-colors"
        :class="editor.isActive('bold') ? 'bg-[color:var(--brand-color)] text-white' : 'text-gray-500 hover:bg-gray-200 dark:hover:bg-gray-700 dark:text-gray-400'"
        :disabled="disabled"
        title="Bold (Ctrl+B)"
        aria-label="Bold"
        @click="editor.chain().focus().toggleBold().run()"
      >
        B
      </button>
      <button
        type="button"
        class="p-1 rounded text-xs italic w-6 h-6 flex items-center justify-center transition-colors"
        :class="editor.isActive('italic') ? 'bg-[color:var(--brand-color)] text-white' : 'text-gray-500 hover:bg-gray-200 dark:hover:bg-gray-700 dark:text-gray-400'"
        :disabled="disabled"
        title="Italic (Ctrl+I)"
        aria-label="Italic"
        @click="editor.chain().focus().toggleItalic().run()"
      >
        I
      </button>
      <div class="w-px h-4 bg-gray-300 dark:bg-gray-600 mx-0.5" />
      <button
        type="button"
        class="p-1 rounded text-xs w-6 h-6 flex items-center justify-center transition-colors"
        :class="editor.isActive('bulletList') ? 'bg-[color:var(--brand-color)] text-white' : 'text-gray-500 hover:bg-gray-200 dark:hover:bg-gray-700 dark:text-gray-400'"
        :disabled="disabled"
        title="Bullet list"
        aria-label="Bullet list"
        @click="editor.chain().focus().toggleBulletList().run()"
      >
        •≡
      </button>
      <button
        type="button"
        class="p-1 rounded text-xs w-6 h-6 flex items-center justify-center transition-colors"
        :class="editor.isActive('orderedList') ? 'bg-[color:var(--brand-color)] text-white' : 'text-gray-500 hover:bg-gray-200 dark:hover:bg-gray-700 dark:text-gray-400'"
        :disabled="disabled"
        title="Numbered list"
        aria-label="Numbered list"
        @click="editor.chain().focus().toggleOrderedList().run()"
      >
        1≡
      </button>
      <div class="w-px h-4 bg-gray-300 dark:bg-gray-600 mx-0.5" />
      <button
        type="button"
        class="p-1 rounded text-xs w-6 h-6 flex items-center justify-center transition-colors text-gray-500 hover:bg-gray-200 dark:hover:bg-gray-700 dark:text-gray-400"
        :disabled="disabled || !editor.can().undo()"
        title="Undo"
        aria-label="Undo"
        @click="editor.chain().focus().undo().run()"
      >
        ↩
      </button>
    </div>

    <!-- Editor area -->
    <EditorContent :editor="editor" />
  </div>
</template>

<style>
/* Tiptap placeholder */
.tiptap p.is-editor-empty:first-child::before {
  content: attr(data-placeholder);
  float: left;
  color: #9ca3af;
  pointer-events: none;
  height: 0;
}
</style>

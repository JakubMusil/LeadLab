<script setup lang="ts">
/**
 * RichTextEditor — Tiptap-based rich-text editor for activity comments.
 *
 * Features:
 *  - Bold, italic, underline formatting
 *  - Ordered and bullet lists
 *  - Placeholder text
 *  - @mention team members with suggestion dropdown (creates a notification)
 *  - Emoji picker
 *  - Exposes plain-text and HTML content via v-model (HTML)
 *  - Exposes getMentionedIds() for the parent to extract mentioned user IDs
 */
import { ref, onBeforeUnmount, onMounted, onUnmounted, watch } from 'vue'
import { useEditor, EditorContent } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import Placeholder from '@tiptap/extension-placeholder'
import Mention from '@tiptap/extension-mention'

export interface MentionUser {
  id: string
  label: string
}

const props = withDefaults(
  defineProps<{
    modelValue: string
    placeholder?: string
    disabled?: boolean
    members?: MentionUser[]
  }>(),
  {
    placeholder: 'Write a comment…',
    disabled: false,
    members: () => [],
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

// ---------------------------------------------------------------------------
// Mention suggestion state
// ---------------------------------------------------------------------------

interface MentionPopupState {
  visible: boolean
  x: number
  y: number
  items: MentionUser[]
  selectedIndex: number
  selectItem: ((index: number) => void) | null
}

const mentionPopup = ref<MentionPopupState>({
  visible: false,
  x: 0,
  y: 0,
  items: [],
  selectedIndex: 0,
  selectItem: null,
})

// ---------------------------------------------------------------------------
// Emoji picker state
// ---------------------------------------------------------------------------

const showEmojiPicker = ref(false)
const COMMON_EMOJIS = [
  '😀', '😊', '😂', '❤️', '👍', '👎', '🎉', '🔥',
  '✅', '❌', '📝', '💡', '⚠️', '🚀', '💬', '👋',
  '🙌', '🤔', '😅', '🙏', '👀', '💪', '🔗', '📎',
]

function insertEmoji(emoji: string) {
  editor.value?.chain().focus().insertContent(emoji).run()
  showEmojiPicker.value = false
}

function closeEmojiOnOutside(e: MouseEvent) {
  if (showEmojiPicker.value) {
    const target = e.target as HTMLElement
    if (!target.closest('[data-emoji-picker]')) {
      showEmojiPicker.value = false
    }
  }
}

onMounted(() => document.addEventListener('click', closeEmojiOnOutside, true))
onUnmounted(() => document.removeEventListener('click', closeEmojiOnOutside, true))

// ---------------------------------------------------------------------------
// Tiptap editor setup
// ---------------------------------------------------------------------------

const editor = useEditor({
  content: props.modelValue,
  editable: !props.disabled,
  extensions: [
    StarterKit,
    Placeholder.configure({ placeholder: props.placeholder }),
    Mention.configure({
      HTMLAttributes: { class: 'mention' },
      suggestion: {
        items: ({ query }: { query: string }) =>
          props.members
            .filter((m) => m.label.toLowerCase().includes(query.toLowerCase()))
            .slice(0, 8),

        render: () => ({
          onStart(suggProps: Record<string, unknown>) {
            const p = suggProps as {
              items: MentionUser[]
              clientRect?: () => DOMRect | null
              command: (attrs: { id: string; label: string }) => void
            }
            const rect = p.clientRect?.()
            if (!rect) return
            mentionPopup.value = {
              visible: true,
              x: rect.left + window.scrollX,
              y: rect.bottom + window.scrollY + 4,
              items: p.items,
              selectedIndex: 0,
              selectItem: (index: number) => {
                const item = mentionPopup.value.items[index]
                if (item) p.command({ id: item.id, label: item.label })
                mentionPopup.value.visible = false
              },
            }
          },
          onUpdate(suggProps: Record<string, unknown>) {
            const p = suggProps as {
              items: MentionUser[]
              clientRect?: () => DOMRect | null
              command: (attrs: { id: string; label: string }) => void
            }
            const rect = p.clientRect?.()
            mentionPopup.value = {
              visible: true,
              x: rect ? rect.left + window.scrollX : mentionPopup.value.x,
              y: rect ? rect.bottom + window.scrollY + 4 : mentionPopup.value.y,
              items: p.items,
              selectedIndex: 0,
              selectItem: (index: number) => {
                const item = mentionPopup.value.items[index]
                if (item) p.command({ id: item.id, label: item.label })
                mentionPopup.value.visible = false
              },
            }
          },
          onKeyDown(suggProps: Record<string, unknown>) {
            const p = suggProps as { event: KeyboardEvent }
            if (p.event.key === 'ArrowUp') {
              mentionPopup.value.selectedIndex = Math.max(0, mentionPopup.value.selectedIndex - 1)
              return true
            }
            if (p.event.key === 'ArrowDown') {
              mentionPopup.value.selectedIndex = Math.min(
                mentionPopup.value.items.length - 1,
                mentionPopup.value.selectedIndex + 1,
              )
              return true
            }
            if (p.event.key === 'Enter') {
              mentionPopup.value.selectItem?.(mentionPopup.value.selectedIndex)
              return true
            }
            return false
          },
          onExit() {
            mentionPopup.value.visible = false
          },
        }),
      },
    }),
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

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

function getMentionedIds(): string[] {
  if (!editor.value) return []
  const ids: string[] = []
  editor.value.state.doc.descendants((node) => {
    if (node.type.name === 'mention') {
      ids.push(node.attrs.id as string)
    }
  })
  return [...new Set(ids)]
}

defineExpose({ getMentionedIds })
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
      <div class="w-px h-4 bg-gray-300 dark:bg-gray-600 mx-0.5" />
      <!-- Emoji picker toggle -->
      <div class="relative" data-emoji-picker>
        <button
          type="button"
          class="p-1 rounded text-sm w-6 h-6 flex items-center justify-center transition-colors text-gray-500 hover:bg-gray-200 dark:hover:bg-gray-700 dark:text-gray-400"
          :disabled="disabled"
          title="Insert emoji"
          aria-label="Insert emoji"
          :aria-expanded="showEmojiPicker"
          @click.stop="showEmojiPicker = !showEmojiPicker"
        >
          😊
        </button>
        <!-- Emoji dropdown -->
        <div
          v-if="showEmojiPicker"
          class="absolute left-0 top-full mt-1 z-50 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl shadow-xl p-2 grid grid-cols-8 gap-0.5 w-48"
          role="listbox"
          aria-label="Emoji picker"
        >
          <button
            v-for="emoji in COMMON_EMOJIS"
            :key="emoji"
            type="button"
            class="w-5 h-5 text-sm flex items-center justify-center rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
            :title="emoji"
            :aria-label="emoji"
            role="option"
            @click.stop="insertEmoji(emoji)"
          >
            {{ emoji }}
          </button>
        </div>
      </div>
    </div>

    <!-- Editor area -->
    <EditorContent :editor="editor" />
  </div>

  <!-- Mention suggestion dropdown (teleported to body for correct z-index) -->
  <Teleport to="body">
    <Transition
      enter-active-class="transition-all duration-100 ease-out"
      enter-from-class="opacity-0 scale-95"
      enter-to-class="opacity-100 scale-100"
      leave-active-class="transition-all duration-75 ease-in"
      leave-from-class="opacity-100 scale-100"
      leave-to-class="opacity-0 scale-95"
    >
      <div
        v-if="mentionPopup.visible && mentionPopup.items.length > 0"
        class="fixed z-[300] min-w-[180px] bg-white dark:bg-gray-800 rounded-xl shadow-xl border border-gray-200 dark:border-gray-700 py-1 overflow-hidden"
        :style="{ top: `${mentionPopup.y}px`, left: `${mentionPopup.x}px` }"
        role="listbox"
        aria-label="Mention suggestions"
      >
        <button
          v-for="(item, index) in mentionPopup.items"
          :key="item.id"
          type="button"
          class="w-full flex items-center gap-2 px-3 py-1.5 text-sm text-left transition-colors"
          :class="index === mentionPopup.selectedIndex
            ? 'bg-[color:var(--brand-color)] text-white'
            : 'text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700'"
          role="option"
          :aria-selected="index === mentionPopup.selectedIndex"
          @mouseenter="mentionPopup.selectedIndex = index"
          @click="mentionPopup.selectItem?.(index)"
        >
          <span class="w-6 h-6 rounded-full bg-gray-200 dark:bg-gray-600 flex items-center justify-center text-xs font-bold flex-shrink-0">
            {{ item.label.charAt(0).toUpperCase() }}
          </span>
          <span class="truncate">{{ item.label }}</span>
        </button>
      </div>
    </Transition>
  </Teleport>
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

/* Mention node styling */
.tiptap .mention {
  background-color: color-mix(in srgb, var(--brand-color) 15%, transparent);
  color: var(--brand-color);
  border-radius: 0.25rem;
  padding: 0 0.2em;
  font-weight: 500;
}
</style>


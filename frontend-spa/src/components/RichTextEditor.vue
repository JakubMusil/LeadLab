<script setup lang="ts">
/**
 * RichTextEditor — Tiptap-based rich-text editor for activity comments.
 *
 * Features:
 *  - Bold, italic, underline formatting
 *  - Headings (H1, H2, H3)
 *  - Ordered and bullet lists
 *  - Placeholder text
 *  - @mention team members with suggestion dropdown (creates a notification)
 *  - Emoji picker
 *  - Text color and background (highlight) color pickers
 *  - Link insertion
 *  - Table insertion
 *  - Image and file attachment upload (images inline, files as download links)
 *  - Exposes plain-text and HTML content via v-model (HTML)
 *  - Exposes getMentionedIds() for the parent to extract mentioned user IDs
 */
import { ref, onBeforeUnmount, onMounted, onUnmounted, watch } from 'vue'
import { useEditor, EditorContent } from '@tiptap/vue-3'
import { useToast } from '@/composables/useToast'
import StarterKit from '@tiptap/starter-kit'
import Placeholder from '@tiptap/extension-placeholder'
import Mention from '@tiptap/extension-mention'
import Image from '@tiptap/extension-image'
import TaskList from '@tiptap/extension-task-list'
import TaskItem from '@tiptap/extension-task-item'
import { TextStyle } from '@tiptap/extension-text-style'
import { Color } from '@tiptap/extension-color'
import { Highlight } from '@tiptap/extension-highlight'
import { Link } from '@tiptap/extension-link'
import { Table } from '@tiptap/extension-table'
import { TableRow } from '@tiptap/extension-table-row'
import { TableHeader } from '@tiptap/extension-table-header'
import { TableCell } from '@tiptap/extension-table-cell'
import type { SuggestionProps, SuggestionKeyDownProps } from '@tiptap/suggestion'
import {
  PaperClipIcon,
  ClipboardDocumentCheckIcon,
  LinkIcon,
  TableCellsIcon,
} from '@heroicons/vue/24/outline'

export interface MentionUser {
  id: string
  label: string
}

export interface UploadedFile {
  id: string
  original_filename: string
  content_type: string
  size_bytes: number
  url: string
  created_at: string
}

/** Shape of one file entry returned by /api/v1/crm/file-uploads/upload */
interface FileUploadEntry {
  document_id: string
  url: string
  filename: string
  content_type: string
  size_bytes: number
}

const props = withDefaults(
  defineProps<{
    modelValue: string
    placeholder?: string
    disabled?: boolean
    members?: MentionUser[]
    uploadUrl?: string
  }>(),
  {
    placeholder: 'Write a comment…',
    disabled: false,
    members: () => [],
    uploadUrl: undefined,
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: string]
  'fileUploaded': [file: UploadedFile]
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
// File upload state
// ---------------------------------------------------------------------------

const fileUploadRef = ref<HTMLInputElement | null>(null)
const isUploading = ref(false)
const toast = useToast()

async function handleFileUpload(e: Event) {
  if (!props.uploadUrl) return
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  input.value = ''

  isUploading.value = true
  try {
    const fd = new FormData()
    fd.append('files', file)
    const res = await fetch(props.uploadUrl, {
      method: 'POST',
      credentials: 'include',
      body: fd,
    })
    if (!res.ok) {
      const errorData = await res.json().catch(() => null)
      toast.error(errorData?.detail ?? 'Upload failed.')
      return
    }
    const body = (await res.json()) as { files: FileUploadEntry[] }
    const entry = body.files?.[0]
    if (!entry) return

    if (file.type.startsWith('image/') || entry.content_type?.startsWith('image/')) {
      editor.value?.chain().focus().setImage({ src: entry.url, alt: entry.filename }).run()
    } else {
      // Non-image files are appended as download links at the end of the document
      const docSize = editor.value?.state.doc.content.size ?? 1
      editor.value
        ?.chain()
        .insertContentAt(docSize - 1, {
          type: 'paragraph',
          content: [
            {
              type: 'text',
              marks: [
                {
                  type: 'link',
                  attrs: {
                    href: entry.url,
                    target: '_blank',
                    rel: 'noopener noreferrer',
                    download: entry.filename,
                  },
                },
              ],
              text: `📎 ${entry.filename}`,
            },
          ],
        })
        .run()
    }
    emit('fileUploaded', {
      id: entry.document_id,
      original_filename: entry.filename,
      content_type: entry.content_type,
      size_bytes: entry.size_bytes,
      url: entry.url,
      created_at: new Date().toISOString(),
    })
  } catch {
    toast.error('Upload failed.')
  } finally {
    isUploading.value = false
  }
}

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
// Color / highlight picker state
// ---------------------------------------------------------------------------

const showColorPicker = ref(false)
const showHighlightPicker = ref(false)

const TEXT_COLORS = [
  '#000000', '#374151', '#ef4444', '#f97316', '#eab308',
  '#22c55e', '#3b82f6', '#8b5cf6', '#ec4899',
]
const HIGHLIGHT_COLORS = [
  'transparent', '#fef08a', '#bbf7d0', '#bfdbfe',
  '#f5d0fe', '#fecaca', '#fed7aa',
]

function setColor(color: string) {
  editor.value?.chain().focus().setColor(color).run()
  showColorPicker.value = false
}

function setHighlight(color: string) {
  if (color === 'transparent') {
    editor.value?.chain().focus().unsetHighlight().run()
  } else {
    editor.value?.chain().focus().setHighlight({ color }).run()
  }
  showHighlightPicker.value = false
}

function closePickersOnOutside(e: MouseEvent) {
  const target = e.target as HTMLElement
  if (showColorPicker.value && !target.closest('[data-color-picker]')) {
    showColorPicker.value = false
  }
  if (showHighlightPicker.value && !target.closest('[data-highlight-picker]')) {
    showHighlightPicker.value = false
  }
  if (showLinkInput.value && !target.closest('[data-link-input]')) {
    showLinkInput.value = false
    linkInputValue.value = ''
  }
}

onMounted(() => document.addEventListener('click', closePickersOnOutside, true))
onUnmounted(() => document.removeEventListener('click', closePickersOnOutside, true))

// ---------------------------------------------------------------------------
// Link insertion — inline popup (accessible alternative to window.prompt)
// ---------------------------------------------------------------------------

const showLinkInput = ref(false)
const linkInputValue = ref('')
const linkInputRef = ref<HTMLInputElement | null>(null)

function openLinkInput() {
  // Pre-fill with existing link href if cursor is inside a link
  const existing = editor.value?.getAttributes('link').href ?? ''
  linkInputValue.value = typeof existing === 'string' ? existing : ''
  showLinkInput.value = true
  // Focus the input on the next tick after the element is rendered
  setTimeout(() => linkInputRef.value?.focus(), 50)
}

function confirmLink() {
  const raw = linkInputValue.value.trim()
  if (!raw) {
    editor.value?.chain().focus().unsetLink().run()
  } else {
    const href = /^https?:\/\//i.test(raw) ? raw : `https://${raw}`
    editor.value?.chain().focus().setLink({ href }).run()
  }
  showLinkInput.value = false
  linkInputValue.value = ''
}

function onLinkInputKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter') {
    e.preventDefault()
    confirmLink()
  } else if (e.key === 'Escape') {
    showLinkInput.value = false
    linkInputValue.value = ''
  }
}

// ---------------------------------------------------------------------------
// Table insertion
// ---------------------------------------------------------------------------

function insertTable() {
  editor.value?.chain().focus().insertTable({ rows: 2, cols: 3, withHeaderRow: true }).run()
}

// ---------------------------------------------------------------------------
// Tiptap editor setup
// ---------------------------------------------------------------------------

const editor = useEditor({
  content: props.modelValue,
  editable: !props.disabled,
  extensions: [
    StarterKit,
    Image.configure({ inline: true, allowBase64: false }),
    Placeholder.configure({ placeholder: props.placeholder }),
    TaskList,
    TaskItem.configure({ nested: false }),
    TextStyle,
    Color,
    Highlight.configure({ multicolor: true }),
    Link.configure({ openOnClick: false }),
    Table.configure({ resizable: false }),
    TableRow,
    TableHeader,
    TableCell,
    Mention.configure({
      HTMLAttributes: { class: 'mention' },
      suggestion: {
        items: ({ query }: { query: string }) =>
          props.members
            .filter((m) => m.label.toLowerCase().includes(query.toLowerCase()))
            .slice(0, 8),

        render: () => ({
          onStart(suggProps: SuggestionProps<MentionUser>) {
            const p = suggProps
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
          onUpdate(suggProps: SuggestionProps<MentionUser>) {
            const p = suggProps
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
          onKeyDown(suggProps: SuggestionKeyDownProps) {
            const p = suggProps
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
        'prose prose-sm dark:prose-invert max-w-none focus:outline-none min-h-[80px] px-3 py-2 text-gray-900 dark:text-gray-100',
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
      editor.value.commands.setContent(val, { emitUpdate: false, parseOptions: { preserveWhitespace: 'full' } })
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
      class="flex items-center flex-wrap gap-0.5 px-2 py-1 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800"
    >
      <!-- Headings -->
      <button
        type="button"
        class="p-1 rounded text-[11px] font-bold w-7 h-6 flex items-center justify-center transition-colors"
        :class="editor.isActive('heading', { level: 1 }) ? 'bg-[color:var(--brand-color)] text-white' : 'text-gray-500 hover:bg-gray-200 dark:hover:bg-gray-700 dark:text-gray-400'"
        :disabled="disabled"
        title="Heading 1"
        aria-label="Heading 1"
        @click="editor.chain().focus().toggleHeading({ level: 1 }).run()"
      >H1</button>
      <button
        type="button"
        class="p-1 rounded text-[11px] font-bold w-7 h-6 flex items-center justify-center transition-colors"
        :class="editor.isActive('heading', { level: 2 }) ? 'bg-[color:var(--brand-color)] text-white' : 'text-gray-500 hover:bg-gray-200 dark:hover:bg-gray-700 dark:text-gray-400'"
        :disabled="disabled"
        title="Heading 2"
        aria-label="Heading 2"
        @click="editor.chain().focus().toggleHeading({ level: 2 }).run()"
      >H2</button>
      <button
        type="button"
        class="p-1 rounded text-[11px] font-bold w-7 h-6 flex items-center justify-center transition-colors"
        :class="editor.isActive('heading', { level: 3 }) ? 'bg-[color:var(--brand-color)] text-white' : 'text-gray-500 hover:bg-gray-200 dark:hover:bg-gray-700 dark:text-gray-400'"
        :disabled="disabled"
        title="Heading 3"
        aria-label="Heading 3"
        @click="editor.chain().focus().toggleHeading({ level: 3 }).run()"
      >H3</button>
      <div class="w-px h-4 bg-gray-300 dark:bg-gray-600 mx-0.5" />

      <!-- Bold / Italic -->
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

      <!-- Lists + Checklist -->
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
      <button
        type="button"
        class="p-1 rounded w-6 h-6 flex items-center justify-center transition-colors"
        :class="editor.isActive('taskList') ? 'bg-[color:var(--brand-color)] text-white' : 'text-gray-500 hover:bg-gray-200 dark:hover:bg-gray-700 dark:text-gray-400'"
        :disabled="disabled"
        title="Checklist"
        aria-label="Checklist"
        @click="editor.chain().focus().toggleTaskList().run()"
      >
        <ClipboardDocumentCheckIcon class="w-3.5 h-3.5" />
      </button>
      <div class="w-px h-4 bg-gray-300 dark:bg-gray-600 mx-0.5" />

      <!-- Text color picker -->
      <div class="relative" data-color-picker>
        <button
          type="button"
          class="p-1 rounded w-6 h-6 flex items-center justify-center transition-colors text-gray-500 hover:bg-gray-200 dark:hover:bg-gray-700 dark:text-gray-400"
          :disabled="disabled"
          title="Text color"
          aria-label="Text color"
          :aria-expanded="showColorPicker"
          @click.stop="showColorPicker = !showColorPicker; showHighlightPicker = false"
        >
          <span class="text-xs font-bold leading-none" style="text-decoration: underline; text-decoration-style: solid; text-decoration-color: currentColor;">A</span>
        </button>
        <div
          v-if="showColorPicker"
          class="absolute left-0 top-full mt-1 z-50 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl shadow-xl p-2 grid grid-cols-5 gap-1 w-28"
          role="listbox"
          aria-label="Text color picker"
        >
          <button
            v-for="color in TEXT_COLORS"
            :key="color"
            type="button"
            class="w-5 h-5 rounded-full border border-gray-300 dark:border-gray-600 transition-transform hover:scale-110 focus:outline-none focus:ring-1 focus:ring-offset-1"
            :style="{ backgroundColor: color }"
            :title="color"
            :aria-label="color"
            role="option"
            @click.stop="setColor(color)"
          />
        </div>
      </div>

      <!-- Highlight (background) color picker -->
      <div class="relative" data-highlight-picker>
        <button
          type="button"
          class="p-1 rounded w-6 h-6 flex items-center justify-center transition-colors text-gray-500 hover:bg-gray-200 dark:hover:bg-gray-700 dark:text-gray-400"
          :disabled="disabled"
          title="Highlight color"
          aria-label="Highlight color"
          :aria-expanded="showHighlightPicker"
          @click.stop="showHighlightPicker = !showHighlightPicker; showColorPicker = false"
        >
          <span class="text-xs font-bold leading-none px-0.5 rounded" style="background-color: #fef08a; color: #000;">A</span>
        </button>
        <div
          v-if="showHighlightPicker"
          class="absolute left-0 top-full mt-1 z-50 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl shadow-xl p-2 grid grid-cols-4 gap-1 w-24"
          role="listbox"
          aria-label="Highlight color picker"
        >
          <button
            v-for="color in HIGHLIGHT_COLORS"
            :key="color"
            type="button"
            class="w-5 h-5 rounded border border-gray-300 dark:border-gray-600 transition-transform hover:scale-110 focus:outline-none focus:ring-1 focus:ring-offset-1 flex items-center justify-center text-[10px]"
            :style="color !== 'transparent' ? { backgroundColor: color } : {}"
            :title="color === 'transparent' ? 'Remove highlight' : color"
            :aria-label="color === 'transparent' ? 'Remove highlight' : color"
            role="option"
            @click.stop="setHighlight(color)"
          >
            <span v-if="color === 'transparent'" class="text-gray-400 text-[10px]">✕</span>
          </button>
        </div>
      </div>
      <div class="w-px h-4 bg-gray-300 dark:bg-gray-600 mx-0.5" />

      <!-- Link -->
      <div class="relative" data-link-input>
        <button
          type="button"
          class="p-1 rounded w-6 h-6 flex items-center justify-center transition-colors"
          :class="editor.isActive('link') ? 'bg-[color:var(--brand-color)] text-white' : 'text-gray-500 hover:bg-gray-200 dark:hover:bg-gray-700 dark:text-gray-400'"
          :disabled="disabled"
          title="Insert link"
          aria-label="Insert link"
          :aria-expanded="showLinkInput"
          @click.stop="openLinkInput"
        >
          <LinkIcon class="w-3.5 h-3.5" />
        </button>
        <!-- Link URL input popup -->
        <div
          v-if="showLinkInput"
          class="absolute left-0 top-full mt-1 z-50 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl shadow-xl p-2 flex items-center gap-1 min-w-[220px]"
          role="dialog"
          aria-label="Insert link"
        >
          <input
            ref="linkInputRef"
            v-model="linkInputValue"
            type="url"
            placeholder="https://…"
            class="flex-1 text-xs rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1 focus:outline-none focus:border-[color:var(--brand-color)]"
            aria-label="URL"
            @keydown="onLinkInputKeydown"
          />
          <button
            type="button"
            class="px-2 py-1 rounded-lg bg-[color:var(--brand-color)] text-white text-xs font-medium"
            @click.stop="confirmLink"
          >OK</button>
        </div>
      </div>

      <!-- Table -->
      <button
        type="button"
        class="p-1 rounded w-6 h-6 flex items-center justify-center transition-colors text-gray-500 hover:bg-gray-200 dark:hover:bg-gray-700 dark:text-gray-400"
        :disabled="disabled"
        title="Insert table"
        aria-label="Insert table"
        @click="insertTable"
      >
        <TableCellsIcon class="w-3.5 h-3.5" />
      </button>
      <div class="w-px h-4 bg-gray-300 dark:bg-gray-600 mx-0.5" />

      <!-- Undo -->
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
      <!-- File / image upload (only when uploadUrl is provided) -->
      <template v-if="uploadUrl">
        <div class="w-px h-4 bg-gray-300 dark:bg-gray-600 mx-0.5" />
        <button
          type="button"
          class="p-1 rounded w-6 h-6 flex items-center justify-center transition-colors text-gray-500 hover:bg-gray-200 dark:hover:bg-gray-700 dark:text-gray-400"
          :class="{ 'opacity-50 cursor-not-allowed': isUploading }"
          :disabled="disabled || isUploading"
          title="Attach file or image"
          aria-label="Attach file or image"
          @click="fileUploadRef?.click()"
        >
          <PaperClipIcon class="w-3.5 h-3.5" />
        </button>
        <input
          ref="fileUploadRef"
          type="file"
          class="hidden"
          aria-hidden="true"
          @change="handleFileUpload"
        />
      </template>
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
/* Tiptap placeholder — color must keep ≥ 4.5:1 contrast on white background.
   gray-500 (#6b7280) on white is ~4.83:1, passes WCAG AA for normal text. */
.tiptap p.is-editor-empty:first-child::before {
  content: attr(data-placeholder);
  float: left;
  color: #6b7280;
  pointer-events: none;
  height: 0;
}
.dark .tiptap p.is-editor-empty:first-child::before {
  color: #9ca3af;
}

/* Mention node styling */
.tiptap .mention {
  background-color: color-mix(in srgb, var(--brand-color) 15%, transparent);
  color: var(--brand-color);
  border-radius: 0.25rem;
  padding: 0 0.2em;
  font-weight: 500;
}

/* Task list (checklist) styling in the editor */
.tiptap ul[data-type="taskList"] {
  list-style: none;
  padding-left: 0;
  margin-left: 0;
}
.tiptap ul[data-type="taskList"] > li {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.2rem 0.375rem;
  border-radius: 0.375rem;
  transition: background-color 0.15s ease;
}
.tiptap ul[data-type="taskList"] > li:hover {
  background-color: rgba(0, 0, 0, 0.03);
}
.tiptap ul[data-type="taskList"] > li > label {
  flex: 0 0 auto;
  user-select: none;
  cursor: pointer;
  display: flex;
  align-items: center;
}
.tiptap ul[data-type="taskList"] > li > label > input[type="checkbox"] {
  width: 0.9rem;
  height: 0.9rem;
  cursor: pointer;
  accent-color: var(--brand-color);
}
.tiptap ul[data-type="taskList"] > li > label > span {
  display: none;
}
.tiptap ul[data-type="taskList"] > li > div {
  flex: 1 1 auto;
  min-width: 0;
}
.tiptap ul[data-type="taskList"] > li > div p {
  transition: color 0.15s ease;
}
.tiptap ul[data-type="taskList"] > li[data-checked="true"] > div p {
  text-decoration: line-through;
  text-decoration-color: #9ca3af;
  color: #9ca3af;
}

/* Table styling */
.tiptap table {
  border-collapse: collapse;
  width: 100%;
  margin: 0.5rem 0;
  table-layout: fixed;
}
.tiptap table td,
.tiptap table th {
  border: 1px solid #d1d5db;
  padding: 0.3rem 0.5rem;
  vertical-align: top;
  min-width: 2rem;
  box-sizing: border-box;
  position: relative;
}
.dark .tiptap table td,
.dark .tiptap table th {
  border-color: #4b5563;
}
.tiptap table th {
  background-color: #f9fafb;
  font-weight: 600;
  text-align: left;
}
.dark .tiptap table th {
  background-color: #1f2937;
}
.tiptap table .selectedCell:after {
  background: rgba(59, 130, 246, 0.15);
  content: '';
  left: 0;
  right: 0;
  top: 0;
  bottom: 0;
  pointer-events: none;
  position: absolute;
  z-index: 2;
}

/* Link styling */
.tiptap a {
  color: var(--brand-color);
  text-decoration: underline;
  text-underline-offset: 2px;
}
.tiptap a:hover {
  opacity: 0.8;
}
</style>


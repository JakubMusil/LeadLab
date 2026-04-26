/// <reference types="../../../../../../.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
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
import { ref, onBeforeUnmount, onMounted, onUnmounted, watch } from 'vue';
import { useEditor, EditorContent } from '@tiptap/vue-3';
import StarterKit from '@tiptap/starter-kit';
import Placeholder from '@tiptap/extension-placeholder';
import Mention from '@tiptap/extension-mention';
const props = withDefaults(defineProps(), {
    placeholder: 'Write a comment…',
    disabled: false,
    members: () => [],
});
const emit = defineEmits();
const mentionPopup = ref({
    visible: false,
    x: 0,
    y: 0,
    items: [],
    selectedIndex: 0,
    selectItem: null,
});
// ---------------------------------------------------------------------------
// Emoji picker state
// ---------------------------------------------------------------------------
const showEmojiPicker = ref(false);
const COMMON_EMOJIS = [
    '😀', '😊', '😂', '❤️', '👍', '👎', '🎉', '🔥',
    '✅', '❌', '📝', '💡', '⚠️', '🚀', '💬', '👋',
    '🙌', '🤔', '😅', '🙏', '👀', '💪', '🔗', '📎',
];
function insertEmoji(emoji) {
    editor.value?.chain().focus().insertContent(emoji).run();
    showEmojiPicker.value = false;
}
function closeEmojiOnOutside(e) {
    if (showEmojiPicker.value) {
        const target = e.target;
        if (!target.closest('[data-emoji-picker]')) {
            showEmojiPicker.value = false;
        }
    }
}
onMounted(() => document.addEventListener('click', closeEmojiOnOutside, true));
onUnmounted(() => document.removeEventListener('click', closeEmojiOnOutside, true));
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
                items: ({ query }) => props.members
                    .filter((m) => m.label.toLowerCase().includes(query.toLowerCase()))
                    .slice(0, 8),
                render: () => ({
                    onStart(suggProps) {
                        const p = suggProps;
                        const rect = p.clientRect?.();
                        if (!rect)
                            return;
                        mentionPopup.value = {
                            visible: true,
                            x: rect.left + window.scrollX,
                            y: rect.bottom + window.scrollY + 4,
                            items: p.items,
                            selectedIndex: 0,
                            selectItem: (index) => {
                                const item = mentionPopup.value.items[index];
                                if (item)
                                    p.command({ id: item.id, label: item.label });
                                mentionPopup.value.visible = false;
                            },
                        };
                    },
                    onUpdate(suggProps) {
                        const p = suggProps;
                        const rect = p.clientRect?.();
                        mentionPopup.value = {
                            visible: true,
                            x: rect ? rect.left + window.scrollX : mentionPopup.value.x,
                            y: rect ? rect.bottom + window.scrollY + 4 : mentionPopup.value.y,
                            items: p.items,
                            selectedIndex: 0,
                            selectItem: (index) => {
                                const item = mentionPopup.value.items[index];
                                if (item)
                                    p.command({ id: item.id, label: item.label });
                                mentionPopup.value.visible = false;
                            },
                        };
                    },
                    onKeyDown(suggProps) {
                        const p = suggProps;
                        if (p.event.key === 'ArrowUp') {
                            mentionPopup.value.selectedIndex = Math.max(0, mentionPopup.value.selectedIndex - 1);
                            return true;
                        }
                        if (p.event.key === 'ArrowDown') {
                            mentionPopup.value.selectedIndex = Math.min(mentionPopup.value.items.length - 1, mentionPopup.value.selectedIndex + 1);
                            return true;
                        }
                        if (p.event.key === 'Enter') {
                            mentionPopup.value.selectItem?.(mentionPopup.value.selectedIndex);
                            return true;
                        }
                        return false;
                    },
                    onExit() {
                        mentionPopup.value.visible = false;
                    },
                }),
            },
        }),
    ],
    editorProps: {
        attributes: {
            class: 'prose prose-sm dark:prose-invert max-w-none focus:outline-none min-h-[80px] px-3 py-2',
        },
    },
    onUpdate({ editor }) {
        emit('update:modelValue', editor.getHTML());
    },
});
watch(() => props.modelValue, (val) => {
    if (editor.value && editor.value.getHTML() !== val) {
        editor.value.commands.setContent(val, false, { preserveWhitespace: 'full' });
    }
});
watch(() => props.disabled, (disabled) => {
    editor.value?.setEditable(!disabled);
});
onBeforeUnmount(() => {
    editor.value?.destroy();
});
// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------
function getMentionedIds() {
    if (!editor.value)
        return [];
    const ids = [];
    editor.value.state.doc.descendants((node) => {
        if (node.type.name === 'mention') {
            ids.push(node.attrs.id);
        }
    });
    return [...new Set(ids)];
}
const __VLS_exposed = { getMentionedIds };
defineExpose(__VLS_exposed);
const __VLS_defaults = {
    placeholder: 'Write a comment…',
    disabled: false,
    members: () => [],
};
const __VLS_ctx = {
    ...{},
    ...{},
    ...{},
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "border border-gray-300 dark:border-gray-600 rounded-lg overflow-hidden bg-white dark:bg-gray-900 focus-within:ring-2 focus-within:ring-[color:var(--brand-color)] focus-within:border-transparent transition-shadow" },
    ...{ class: ({ 'opacity-60 cursor-not-allowed': __VLS_ctx.disabled }) },
});
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-300']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['overflow-hidden']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:bg-gray-900']} */ ;
/** @type {__VLS_StyleScopedClasses['focus-within:ring-2']} */ ;
/** @type {__VLS_StyleScopedClasses['focus-within:ring-[color:var(--brand-color)]']} */ ;
/** @type {__VLS_StyleScopedClasses['focus-within:border-transparent']} */ ;
/** @type {__VLS_StyleScopedClasses['transition-shadow']} */ ;
/** @type {__VLS_StyleScopedClasses['opacity-60']} */ ;
/** @type {__VLS_StyleScopedClasses['cursor-not-allowed']} */ ;
if (__VLS_ctx.editor) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "flex items-center gap-0.5 px-2 py-1 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800" },
    });
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-0.5']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-b']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:border-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-gray-50']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:bg-gray-800']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.editor))
                    return;
                __VLS_ctx.editor.chain().focus().toggleBold().run();
                // @ts-ignore
                [disabled, editor, editor,];
            } },
        type: "button",
        ...{ class: "p-1 rounded text-xs font-bold w-6 h-6 flex items-center justify-center transition-colors" },
        ...{ class: (__VLS_ctx.editor.isActive('bold') ? 'bg-[color:var(--brand-color)] text-white' : 'text-gray-500 hover:bg-gray-200 dark:hover:bg-gray-700 dark:text-gray-400') },
        disabled: (__VLS_ctx.disabled),
        title: "Bold (Ctrl+B)",
        'aria-label': "Bold",
    });
    /** @type {__VLS_StyleScopedClasses['p-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
    /** @type {__VLS_StyleScopedClasses['w-6']} */ ;
    /** @type {__VLS_StyleScopedClasses['h-6']} */ ;
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.editor))
                    return;
                __VLS_ctx.editor.chain().focus().toggleItalic().run();
                // @ts-ignore
                [disabled, editor, editor,];
            } },
        type: "button",
        ...{ class: "p-1 rounded text-xs italic w-6 h-6 flex items-center justify-center transition-colors" },
        ...{ class: (__VLS_ctx.editor.isActive('italic') ? 'bg-[color:var(--brand-color)] text-white' : 'text-gray-500 hover:bg-gray-200 dark:hover:bg-gray-700 dark:text-gray-400') },
        disabled: (__VLS_ctx.disabled),
        title: "Italic (Ctrl+I)",
        'aria-label': "Italic",
    });
    /** @type {__VLS_StyleScopedClasses['p-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['italic']} */ ;
    /** @type {__VLS_StyleScopedClasses['w-6']} */ ;
    /** @type {__VLS_StyleScopedClasses['h-6']} */ ;
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div)({
        ...{ class: "w-px h-4 bg-gray-300 dark:bg-gray-600 mx-0.5" },
    });
    /** @type {__VLS_StyleScopedClasses['w-px']} */ ;
    /** @type {__VLS_StyleScopedClasses['h-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-gray-300']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:bg-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['mx-0.5']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.editor))
                    return;
                __VLS_ctx.editor.chain().focus().toggleBulletList().run();
                // @ts-ignore
                [disabled, editor, editor,];
            } },
        type: "button",
        ...{ class: "p-1 rounded text-xs w-6 h-6 flex items-center justify-center transition-colors" },
        ...{ class: (__VLS_ctx.editor.isActive('bulletList') ? 'bg-[color:var(--brand-color)] text-white' : 'text-gray-500 hover:bg-gray-200 dark:hover:bg-gray-700 dark:text-gray-400') },
        disabled: (__VLS_ctx.disabled),
        title: "Bullet list",
        'aria-label': "Bullet list",
    });
    /** @type {__VLS_StyleScopedClasses['p-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['w-6']} */ ;
    /** @type {__VLS_StyleScopedClasses['h-6']} */ ;
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.editor))
                    return;
                __VLS_ctx.editor.chain().focus().toggleOrderedList().run();
                // @ts-ignore
                [disabled, editor, editor,];
            } },
        type: "button",
        ...{ class: "p-1 rounded text-xs w-6 h-6 flex items-center justify-center transition-colors" },
        ...{ class: (__VLS_ctx.editor.isActive('orderedList') ? 'bg-[color:var(--brand-color)] text-white' : 'text-gray-500 hover:bg-gray-200 dark:hover:bg-gray-700 dark:text-gray-400') },
        disabled: (__VLS_ctx.disabled),
        title: "Numbered list",
        'aria-label': "Numbered list",
    });
    /** @type {__VLS_StyleScopedClasses['p-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['w-6']} */ ;
    /** @type {__VLS_StyleScopedClasses['h-6']} */ ;
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div)({
        ...{ class: "w-px h-4 bg-gray-300 dark:bg-gray-600 mx-0.5" },
    });
    /** @type {__VLS_StyleScopedClasses['w-px']} */ ;
    /** @type {__VLS_StyleScopedClasses['h-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-gray-300']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:bg-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['mx-0.5']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.editor))
                    return;
                __VLS_ctx.editor.chain().focus().undo().run();
                // @ts-ignore
                [disabled, editor, editor,];
            } },
        type: "button",
        ...{ class: "p-1 rounded text-xs w-6 h-6 flex items-center justify-center transition-colors text-gray-500 hover:bg-gray-200 dark:hover:bg-gray-700 dark:text-gray-400" },
        disabled: (__VLS_ctx.disabled || !__VLS_ctx.editor.can().undo()),
        title: "Undo",
        'aria-label': "Undo",
    });
    /** @type {__VLS_StyleScopedClasses['p-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['w-6']} */ ;
    /** @type {__VLS_StyleScopedClasses['h-6']} */ ;
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:bg-gray-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:hover:bg-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div)({
        ...{ class: "w-px h-4 bg-gray-300 dark:bg-gray-600 mx-0.5" },
    });
    /** @type {__VLS_StyleScopedClasses['w-px']} */ ;
    /** @type {__VLS_StyleScopedClasses['h-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-gray-300']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:bg-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['mx-0.5']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "relative" },
        'data-emoji-picker': true,
    });
    /** @type {__VLS_StyleScopedClasses['relative']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.editor))
                    return;
                __VLS_ctx.showEmojiPicker = !__VLS_ctx.showEmojiPicker;
                // @ts-ignore
                [disabled, editor, showEmojiPicker, showEmojiPicker,];
            } },
        type: "button",
        ...{ class: "p-1 rounded text-sm w-6 h-6 flex items-center justify-center transition-colors text-gray-500 hover:bg-gray-200 dark:hover:bg-gray-700 dark:text-gray-400" },
        disabled: (__VLS_ctx.disabled),
        title: "Insert emoji",
        'aria-label': "Insert emoji",
        'aria-expanded': (__VLS_ctx.showEmojiPicker),
    });
    /** @type {__VLS_StyleScopedClasses['p-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['w-6']} */ ;
    /** @type {__VLS_StyleScopedClasses['h-6']} */ ;
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:bg-gray-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:hover:bg-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
    if (__VLS_ctx.showEmojiPicker) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "absolute left-0 top-full mt-1 z-50 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl shadow-xl p-2 grid grid-cols-8 gap-0.5 w-48" },
            role: "listbox",
            'aria-label': "Emoji picker",
        });
        /** @type {__VLS_StyleScopedClasses['absolute']} */ ;
        /** @type {__VLS_StyleScopedClasses['left-0']} */ ;
        /** @type {__VLS_StyleScopedClasses['top-full']} */ ;
        /** @type {__VLS_StyleScopedClasses['mt-1']} */ ;
        /** @type {__VLS_StyleScopedClasses['z-50']} */ ;
        /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:bg-gray-800']} */ ;
        /** @type {__VLS_StyleScopedClasses['border']} */ ;
        /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:border-gray-700']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
        /** @type {__VLS_StyleScopedClasses['shadow-xl']} */ ;
        /** @type {__VLS_StyleScopedClasses['p-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['grid']} */ ;
        /** @type {__VLS_StyleScopedClasses['grid-cols-8']} */ ;
        /** @type {__VLS_StyleScopedClasses['gap-0.5']} */ ;
        /** @type {__VLS_StyleScopedClasses['w-48']} */ ;
        for (const [emoji] of __VLS_vFor((__VLS_ctx.COMMON_EMOJIS))) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
                ...{ onClick: (...[$event]) => {
                        if (!(__VLS_ctx.editor))
                            return;
                        if (!(__VLS_ctx.showEmojiPicker))
                            return;
                        __VLS_ctx.insertEmoji(emoji);
                        // @ts-ignore
                        [disabled, showEmojiPicker, showEmojiPicker, COMMON_EMOJIS, insertEmoji,];
                    } },
                key: (emoji),
                type: "button",
                ...{ class: "w-5 h-5 text-sm flex items-center justify-center rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors" },
                title: (emoji),
                'aria-label': (emoji),
                role: "option",
            });
            /** @type {__VLS_StyleScopedClasses['w-5']} */ ;
            /** @type {__VLS_StyleScopedClasses['h-5']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
            /** @type {__VLS_StyleScopedClasses['flex']} */ ;
            /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
            /** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded']} */ ;
            /** @type {__VLS_StyleScopedClasses['hover:bg-gray-100']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:hover:bg-gray-700']} */ ;
            /** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
            (emoji);
            // @ts-ignore
            [];
        }
    }
}
let __VLS_0;
/** @ts-ignore @type {typeof __VLS_components.EditorContent} */
EditorContent;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    editor: (__VLS_ctx.editor),
}));
const __VLS_2 = __VLS_1({
    editor: (__VLS_ctx.editor),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_5;
/** @ts-ignore @type {typeof __VLS_components.Teleport | typeof __VLS_components.Teleport} */
Teleport;
// @ts-ignore
const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
    to: "body",
}));
const __VLS_7 = __VLS_6({
    to: "body",
}, ...__VLS_functionalComponentArgsRest(__VLS_6));
const { default: __VLS_10 } = __VLS_8.slots;
let __VLS_11;
/** @ts-ignore @type {typeof __VLS_components.Transition | typeof __VLS_components.Transition} */
Transition;
// @ts-ignore
const __VLS_12 = __VLS_asFunctionalComponent1(__VLS_11, new __VLS_11({
    enterActiveClass: "transition-all duration-100 ease-out",
    enterFromClass: "opacity-0 scale-95",
    enterToClass: "opacity-100 scale-100",
    leaveActiveClass: "transition-all duration-75 ease-in",
    leaveFromClass: "opacity-100 scale-100",
    leaveToClass: "opacity-0 scale-95",
}));
const __VLS_13 = __VLS_12({
    enterActiveClass: "transition-all duration-100 ease-out",
    enterFromClass: "opacity-0 scale-95",
    enterToClass: "opacity-100 scale-100",
    leaveActiveClass: "transition-all duration-75 ease-in",
    leaveFromClass: "opacity-100 scale-100",
    leaveToClass: "opacity-0 scale-95",
}, ...__VLS_functionalComponentArgsRest(__VLS_12));
const { default: __VLS_16 } = __VLS_14.slots;
if (__VLS_ctx.mentionPopup.visible && __VLS_ctx.mentionPopup.items.length > 0) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "fixed z-[300] min-w-[180px] bg-white dark:bg-gray-800 rounded-xl shadow-xl border border-gray-200 dark:border-gray-700 py-1 overflow-hidden" },
        ...{ style: ({ top: `${__VLS_ctx.mentionPopup.y}px`, left: `${__VLS_ctx.mentionPopup.x}px` }) },
        role: "listbox",
        'aria-label': "Mention suggestions",
    });
    /** @type {__VLS_StyleScopedClasses['fixed']} */ ;
    /** @type {__VLS_StyleScopedClasses['z-[300]']} */ ;
    /** @type {__VLS_StyleScopedClasses['min-w-[180px]']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:bg-gray-800']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['shadow-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:border-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['overflow-hidden']} */ ;
    for (const [item, index] of __VLS_vFor((__VLS_ctx.mentionPopup.items))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
            ...{ onMouseenter: (...[$event]) => {
                    if (!(__VLS_ctx.mentionPopup.visible && __VLS_ctx.mentionPopup.items.length > 0))
                        return;
                    __VLS_ctx.mentionPopup.selectedIndex = index;
                    // @ts-ignore
                    [editor, mentionPopup, mentionPopup, mentionPopup, mentionPopup, mentionPopup, mentionPopup,];
                } },
            ...{ onClick: (...[$event]) => {
                    if (!(__VLS_ctx.mentionPopup.visible && __VLS_ctx.mentionPopup.items.length > 0))
                        return;
                    __VLS_ctx.mentionPopup.selectItem?.(index);
                    // @ts-ignore
                    [mentionPopup,];
                } },
            key: (item.id),
            type: "button",
            ...{ class: "w-full flex items-center gap-2 px-3 py-1.5 text-sm text-left transition-colors" },
            ...{ class: (index === __VLS_ctx.mentionPopup.selectedIndex
                    ? 'bg-[color:var(--brand-color)] text-white'
                    : 'text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700') },
            role: "option",
            'aria-selected': (index === __VLS_ctx.mentionPopup.selectedIndex),
        });
        /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
        /** @type {__VLS_StyleScopedClasses['flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
        /** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-left']} */ ;
        /** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "w-6 h-6 rounded-full bg-gray-200 dark:bg-gray-600 flex items-center justify-center text-xs font-bold flex-shrink-0" },
        });
        /** @type {__VLS_StyleScopedClasses['w-6']} */ ;
        /** @type {__VLS_StyleScopedClasses['h-6']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
        /** @type {__VLS_StyleScopedClasses['bg-gray-200']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:bg-gray-600']} */ ;
        /** @type {__VLS_StyleScopedClasses['flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
        /** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
        /** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
        (item.label.charAt(0).toUpperCase());
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "truncate" },
        });
        /** @type {__VLS_StyleScopedClasses['truncate']} */ ;
        (item.label);
        // @ts-ignore
        [mentionPopup, mentionPopup,];
    }
}
// @ts-ignore
[];
var __VLS_14;
// @ts-ignore
[];
var __VLS_8;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    setup: () => (__VLS_exposed),
    __typeEmits: {},
    __defaults: __VLS_defaults,
    __typeProps: {},
});
export default {};

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { EditorView, keymap } from '@codemirror/view'
import { EditorState, EditorSelection, Compartment } from '@codemirror/state'
import { python } from '@codemirror/lang-python'
import { oneDark } from '@codemirror/theme-one-dark'
import { indentWithTab } from '@codemirror/commands'
import { lineNumbers } from '@codemirror/view'

const props = defineProps({
  modelValue: {
    type: String,
    required: true,
  },
  language: {
    type: String,
    default: 'python',
  },
  readonly: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['update:modelValue', 'execute'])

const editorContainer = ref(null)
const cursorPosition = ref({ line: 1, column: 1 })
const isFullscreen = ref(false)
let view = null
const editableCompartment = new Compartment()

const handleKeydown = (e) => {
  if (e.key === 'Escape' && isFullscreen.value && !e.defaultPrevented) {
    isFullscreen.value = false
  }
}

const toggleFullscreen = () => {
  isFullscreen.value = !isFullscreen.value
}

const bracketPairs = {
  '(': ')',
  '[': ']',
  '{': '}',
  '"': '"',
  "'": "'",
}

const bracketKeymap = Object.entries(bracketPairs).map(([open, close]) => ({
  key: open,
  run: (view) => {
    const { state } = view
    const changes = state.changeByRange((range) => ({
      changes: { from: range.from, to: range.to, insert: open + close },
      range: EditorSelection.range(range.from + 1, range.from + 1),
    }))
    view.dispatch(changes)
    return true
  },
}))

const getLanguageExtension = () => {
  if (props.language === 'python') {
    return python()
  }
  return []
}

const updateCursorPosition = (state) => {
  const pos = state.selection.main.head
  const line = state.doc.lineAt(pos)
  cursorPosition.value = {
    line: line.number,
    column: pos - line.from + 1,
  }
}

const createState = (doc) => {
  return EditorState.create({
    doc,
    extensions: [
      lineNumbers(),
      oneDark,
      getLanguageExtension(),
      EditorView.updateListener.of((update) => {
        if (update.docChanged) {
          emit('update:modelValue', update.state.doc.toString())
        }
        if (update.selectionSet) {
          updateCursorPosition(update.state)
        }
      }),
      keymap.of([
        ...bracketKeymap,
        indentWithTab,
        {
          key: 'Ctrl-Enter',
          run: () => {
            emit('execute')
            return true
          },
        },
      ]),
      editableCompartment.of(EditorView.editable.of(!props.readonly)),
    ],
  })
}

onMounted(() => {
  if (editorContainer.value) {
    view = new EditorView({
      state: createState(props.modelValue),
      parent: editorContainer.value,
    })
    updateCursorPosition(view.state)
  }
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
  if (view) {
    view.destroy()
    view = null
  }
})

watch(
  () => props.modelValue,
  (newValue) => {
    if (view && newValue !== view.state.doc.toString()) {
      view.dispatch({
        changes: { from: 0, to: view.state.doc.length, insert: newValue },
      })
    }
  }
)

watch(
  () => props.readonly,
  (readonly) => {
    if (view) {
      view.dispatch({
        effects: editableCompartment.reconfigure(
          EditorView.editable.of(!readonly)
        ),
      })
    }
  }
)
</script>

<template>
  <div
    :class="[
      isFullscreen ? 'fixed inset-0 z-50 bg-gray-900 p-4' : 'relative h-full',
    ]"
  >
    <div
      v-if="!readonly"
      class="absolute top-2 right-2 flex items-center gap-2 z-10"
    >
      <button
        type="button"
        class="text-gray-400 hover:text-white bg-gray-800 hover:bg-gray-700 p-1.5 rounded transition-colors"
        :title="isFullscreen ? '退出全屏' : '全屏'"
        @click="toggleFullscreen"
      >
        <svg
          v-if="!isFullscreen"
          xmlns="http://www.w3.org/2000/svg"
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <path d="M8 3H5a2 2 0 0 0-2 2v3" />
          <path d="M21 8V5a2 2 0 0 0-2-2h-3" />
          <path d="M3 16v3a2 2 0 0 0 2 2h3" />
          <path d="M16 21h3a2 2 0 0 0 2-2v-3" />
        </svg>
        <svg
          v-else
          xmlns="http://www.w3.org/2000/svg"
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <path d="M8 3v3a2 2 0 0 1-2 2H3" />
          <path d="M21 8h-3a2 2 0 0 1-2-2V3" />
          <path d="M3 16h3a2 2 0 0 1 2 2v3" />
          <path d="M16 21v-3a2 2 0 0 1 2-2h3" />
        </svg>
      </button>
      <span class="text-xs text-gray-400 bg-gray-800 px-2 py-1 rounded">
        行 {{ cursorPosition.line }}, 列 {{ cursorPosition.column }}
      </span>
    </div>
    <div
      ref="editorContainer"
      class="w-full h-full overflow-auto rounded-lg border border-gray-700"
      :class="{ 'opacity-75': readonly }"
      :style="{ '--cm-font-size': isFullscreen ? '20px' : '14px' }"
    ></div>
  </div>
</template>

<style scoped>
:deep(.cm-editor) {
  height: 100%;
  border-radius: 0.5rem;
  font-size: var(--cm-font-size, 14px);
  transition: font-size 0.2s ease;
}
:deep(.cm-focused) {
  outline: none;
}
</style>

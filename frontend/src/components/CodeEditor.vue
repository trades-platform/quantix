<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'

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

const emit = defineEmits(['update:modelValue'])

const textarea = ref(null)
const cursorPosition = ref({ line: 1, column: 1 })

const updateCursorPosition = () => {
  if (!textarea.value) return
  const text = textarea.value.value
  const pos = textarea.value.selectionStart
  const lines = text.substring(0, pos).split('\n')
  cursorPosition.value = {
    line: lines.length,
    column: lines[lines.length - 1].length + 1,
  }
}

const handleTab = (event) => {
  if (event.key === 'Tab') {
    event.preventDefault()
    const textarea = event.target
    const start = textarea.selectionStart
    const end = textarea.selectionEnd
    const value = textarea.value

    textarea.value = value.substring(0, start) + '    ' + value.substring(end)
    textarea.selectionStart = textarea.selectionEnd = start + 4

    emit('update:modelValue', textarea.value)
  }
}

// 自动补全括号
const handleAutoClose = (event) => {
  const pair = {
    '(': ')',
    '[': ']',
    '{': '}',
    '"': '"',
    "'": "'",
  }

  if (pair[event.key]) {
    event.preventDefault()
    const textarea = event.target
    const start = textarea.selectionStart
    const end = textarea.selectionEnd
    const value = textarea.value

    textarea.value =
      value.substring(0, start) + event.key + pair[event.key] + value.substring(end)
    textarea.selectionStart = textarea.selectionEnd = start + 1

    emit('update:modelValue', textarea.value)
  }
}

// Ctrl+Enter 快捷键执行
const handleKeyDown = (event) => {
  if (event.ctrlKey && event.key === 'Enter') {
    emit('execute')
  }
}

onMounted(() => {
  if (textarea.value) {
    textarea.value.addEventListener('keydown', handleTab)
    textarea.value.addEventListener('keydown', handleAutoClose)
    textarea.value.addEventListener('keydown', handleKeyDown)
    textarea.value.addEventListener('click', updateCursorPosition)
    textarea.value.addEventListener('keyup', updateCursorPosition)
  }
})

onUnmounted(() => {
  if (textarea.value) {
    textarea.value.removeEventListener('keydown', handleTab)
    textarea.value.removeEventListener('keydown', handleAutoClose)
    textarea.value.removeEventListener('keydown', handleKeyDown)
    textarea.value.removeEventListener('click', updateCursorPosition)
    textarea.value.removeEventListener('keyup', updateCursorPosition)
  }
})
</script>

<template>
  <div class="relative">
    <div
      v-if="!readonly"
      class="absolute top-2 right-2 text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded"
    >
      行 {{ cursorPosition.line }}, 列 {{ cursorPosition.column }}
    </div>
    <textarea
      ref="textarea"
      :value="modelValue"
      @input="emit('update:modelValue', $event.target.value)"
      :readonly="readonly"
      class="w-full h-full font-mono text-sm p-4 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-none bg-gray-50"
      :class="{ 'bg-gray-100': readonly }"
      spellcheck="false"
    ></textarea>
  </div>
</template>

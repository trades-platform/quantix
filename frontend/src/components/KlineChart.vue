<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import { createLightweightRenderer } from '../utils/lightweightRenderer'

const props = defineProps({
  data: {
    type: Array,
    required: true,
  },
  indicators: {
    type: Array,
    default: () => [],
  },
  trades: {
    type: Array,
    default: () => [],
  },
  height: {
    type: String,
    default: '400px',
  },
  darkMode: {
    type: Boolean,
    default: true,
  },
})

const container = ref(null)
let renderer = null
let observer = null

const renderCurrent = () => {
  if (!renderer) return
  renderer.render({ ohlcv: props.data, indicators: props.indicators, trades: props.trades })
}

onMounted(() => {
  renderer = createLightweightRenderer(container.value, { darkMode: props.darkMode })
  renderCurrent()
  observer = new ResizeObserver(() => renderer && renderer.resize())
  if (container.value) observer.observe(container.value)
})

watch(() => [props.data, props.indicators, props.trades], renderCurrent, { deep: true })

onBeforeUnmount(() => {
  observer && observer.disconnect()
  renderer && renderer.dispose()
  renderer = null
})
</script>

<template>
  <div ref="container" class="w-full" :style="{ height }"></div>
</template>

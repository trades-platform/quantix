<script setup>
import { computed } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { CandlestickChart, LineChart, BarChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DataZoomComponent,
  MarkPointComponent,
} from 'echarts/components'
import VChart from 'vue-echarts'
import { buildEChartsOption } from '../utils/echartsBuilder'

use([
  CanvasRenderer,
  CandlestickChart,
  LineChart,
  BarChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DataZoomComponent,
  MarkPointComponent,
])

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
})

const chartOption = computed(() => {
  return buildEChartsOption(props.data, props.indicators, props.trades)
})
</script>

<template>
  <v-chart :style="{ height }" :option="chartOption" autoresize />
</template>

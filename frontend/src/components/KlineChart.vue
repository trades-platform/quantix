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
} from 'echarts/components'
import VChart from 'vue-echarts'

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
])

const props = defineProps({
  data: {
    type: Array,
    required: true,
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
  const klineData = props.data.map((item) => [
    item.timestamp,
    item.open,
    item.close,
    item.low,
    item.high,
  ])

  const ma5 = calculateMA(5, props.data)
  const ma20 = calculateMA(20, props.data)
  const volumes = props.data.map((item) => [
    item.timestamp,
    item.volume,
    item.close > item.open ? 1 : -1,
  ])

  // 买卖点标记
  const markPoints = props.trades.flatMap((trade) => {
    const index = props.data.findIndex(
      (d) => new Date(d.timestamp).getTime() === new Date(trade.timestamp).getTime()
    )
    if (index === -1) return []

    return [
      {
        name: trade.side === 'buy' ? '买入' : '卖出',
        coord: [trade.timestamp, trade.price],
        value: trade.side === 'buy' ? '买' : '卖',
        itemStyle: {
          color: trade.side === 'buy' ? '#ef4444' : '#22c55e',
        },
      },
    ]
  })

  return {
    animation: false,
    legend: {
      data: ['K线', 'MA5', 'MA20', '成交量'],
      top: 10,
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross',
      },
      formatter: (params) => {
        const data = params[0]
        if (!data) return ''

        const kline = props.data[data.dataIndex]
        if (!kline) return ''

        return `
          <div>时间: ${kline.timestamp}</div>
          <div>开盘: ${kline.open?.toFixed(2)}</div>
          <div>收盘: ${kline.close?.toFixed(2)}</div>
          <div>最高: ${kline.high?.toFixed(2)}</div>
          <div>最低: ${kline.low?.toFixed(2)}</div>
          <div>成交量: ${kline.volume?.toLocaleString()}</div>
        `
      },
    },
    grid: [
      {
        left: '10%',
        right: '8%',
        height: '50%',
      },
      {
        left: '10%',
        right: '8%',
        top: '70%',
        height: '16%',
      },
    ],
    xAxis: [
      {
        type: 'category',
        data: props.data.map((item) => item.timestamp),
        scale: true,
        boundaryGap: false,
        axisLine: { onZero: false },
        splitLine: { show: false },
        min: 'dataMin',
        max: 'dataMax',
      },
      {
        type: 'category',
        gridIndex: 1,
        data: props.data.map((item) => item.timestamp),
        scale: true,
        boundaryGap: false,
        axisLine: { onZero: false },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: { show: false },
        min: 'dataMin',
        max: 'dataMax',
      },
    ],
    yAxis: [
      {
        scale: true,
        splitArea: {
          show: true,
        },
      },
      {
        scale: true,
        gridIndex: 1,
        splitNumber: 2,
        axisLabel: { show: false },
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { show: false },
      },
    ],
    dataZoom: [
      {
        type: 'inside',
        xAxisIndex: [0, 1],
        start: 50,
        end: 100,
      },
      {
        show: true,
        xAxisIndex: [0, 1],
        type: 'slider',
        top: '90%',
        start: 50,
        end: 100,
      },
    ],
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        data: klineData,
        itemStyle: {
          color: '#ef4444',
          color0: '#22c55e',
          borderColor: '#ef4444',
          borderColor0: '#22c55e',
        },
        markPoint: {
          data: markPoints,
          symbol: 'arrow',
          symbolSize: 10,
        },
      },
      {
        name: 'MA5',
        type: 'line',
        data: ma5,
        smooth: true,
        lineStyle: {
          opacity: 0.8,
        },
      },
      {
        name: 'MA20',
        type: 'line',
        data: ma20,
        smooth: true,
        lineStyle: {
          opacity: 0.8,
        },
      },
      {
        name: '成交量',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: volumes,
        itemStyle: {
          color: (params) => {
            return params.value[2] > 0 ? '#ef4444' : '#22c55e'
          },
        },
      },
    ],
  }
})

function calculateMA(period, data) {
  const result = []
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) {
      result.push('-')
      continue
    }

    let sum = 0
    for (let j = 0; j < period; j++) {
      sum += data[i - j].close
    }
    result.push((sum / period).toFixed(2))
  }
  return result
}
</script>

<template>
  <v-chart :style="{ height }" :option="chartOption" autoresize />
</template>

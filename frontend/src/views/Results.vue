<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { backtestApi } from '../api'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, CandlestickChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
} from 'echarts/components'
import VChart from 'vue-echarts'

use([
  CanvasRenderer,
  LineChart,
  CandlestickChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
])

const route = useRoute()
const backtestId = computed(() => route.query.id)

const loading = ref(false)
const backtest = ref(null)
const trades = ref([])

const equityChartOption = computed(() => {
  if (!backtest.value?.equity_curve) {
    return {}
  }

  const data = JSON.parse(backtest.value.equity_curve)
  const dates = data.map((d) => d.date)
  const values = data.map((d) => d.value)

  return {
    title: {
      text: '净值曲线',
      left: 'center',
    },
    tooltip: {
      trigger: 'axis',
    },
    xAxis: {
      type: 'category',
      data: dates,
    },
    yAxis: {
      type: 'value',
      name: '净值',
    },
    series: [
      {
        name: '净值',
        type: 'line',
        data: values,
        smooth: true,
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(59, 130, 246, 0.3)' },
              { offset: 1, color: 'rgba(59, 130, 246, 0)' },
            ],
          },
        },
      },
    ],
  }
})

const fetchBacktest = async () => {
  if (!backtestId.value) return

  loading.value = true
  try {
    const response = await backtestApi.get(backtestId.value)
    backtest.value = response.data
    await fetchTrades()
  } catch (error) {
    console.error('获取回测结果失败:', error)
  } finally {
    loading.value = false
  }
}

const fetchTrades = async () => {
  try {
    const response = await backtestApi.getTrades(backtestId.value)
    trades.value = response.data
  } catch (error) {
    console.error('获取交易明细失败:', error)
  }
}

const formatPercent = (value) => {
  if (value === null || value === undefined) return '-'
  return (value * 100).toFixed(2) + '%'
}

onMounted(() => {
  fetchBacktest()
})
</script>

<template>
  <div class="p-8">
    <h1 class="text-3xl font-bold text-gray-900">回测结果</h1>
    <p class="mt-2 text-gray-600">查看策略回测的详细分析报告</p>

    <div v-if="loading" class="mt-8 text-center py-12">
      <div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      <p class="mt-2 text-gray-600">加载中...</p>
    </div>

    <div v-else-if="backtest">
      <!-- 绩效指标卡片 -->
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mt-8">
        <div class="bg-white rounded-lg shadow p-6">
          <p class="text-sm text-gray-600">总收益率</p>
          <p
            class="text-2xl font-bold mt-2"
            :class="backtest.total_return >= 0 ? 'text-red-600' : 'text-green-600'"
          >
            {{ formatPercent(backtest.total_return) }}
          </p>
        </div>
        <div class="bg-white rounded-lg shadow p-6">
          <p class="text-sm text-gray-600">年化收益</p>
          <p
            class="text-2xl font-bold mt-2"
            :class="backtest.annual_return >= 0 ? 'text-red-600' : 'text-green-600'"
          >
            {{ formatPercent(backtest.annual_return) }}
          </p>
        </div>
        <div class="bg-white rounded-lg shadow p-6">
          <p class="text-sm text-gray-600">夏普比率</p>
          <p class="text-2xl font-bold mt-2 text-blue-600">
            {{ backtest.sharpe_ratio?.toFixed(2) || '-' }}
          </p>
        </div>
        <div class="bg-white rounded-lg shadow p-6">
          <p class="text-sm text-gray-600">最大回撤</p>
          <p class="text-2xl font-bold mt-2 text-green-600">
            {{ formatPercent(backtest.max_drawdown) }}
          </p>
        </div>
      </div>

      <!-- 更多指标 -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mt-6">
        <div class="bg-white rounded-lg shadow p-6">
          <p class="text-sm text-gray-600">胜率</p>
          <p class="text-xl font-bold mt-2 text-purple-600">
            {{ formatPercent(backtest.win_rate) }}
          </p>
        </div>
        <div class="bg-white rounded-lg shadow p-6">
          <p class="text-sm text-gray-600">回测状态</p>
          <p class="text-xl font-bold mt-2" :class="backtest.status === 'completed' ? 'text-green-600' : 'text-yellow-600'">
            {{ backtest.status === 'completed' ? '已完成' : '运行中' }}
          </p>
        </div>
        <div class="bg-white rounded-lg shadow p-6">
          <p class="text-sm text-gray-600">回测时间</p>
          <p class="text-xl font-bold mt-2 text-gray-900">
            {{ new Date(backtest.created_at).toLocaleString() }}
          </p>
        </div>
      </div>

      <!-- 净值曲线图 -->
      <div class="mt-8 bg-white rounded-lg shadow p-6">
        <v-chart class="h-96" :option="equityChartOption" autoresize />
      </div>

      <!-- 交易明细 -->
      <div class="mt-8 bg-white rounded-lg shadow overflow-hidden">
        <div class="px-6 py-4 border-b">
          <h2 class="text-lg font-semibold">交易明细</h2>
        </div>
        <table class="min-w-full">
          <thead class="bg-gray-50">
            <tr>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">时间</th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">标的</th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">方向</th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">价格</th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">数量</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-200">
            <tr v-if="trades.length === 0">
              <td colspan="5" class="px-6 py-4 text-center text-gray-500">暂无交易记录</td>
            </tr>
            <tr v-else v-for="trade in trades" :key="trade.id" class="hover:bg-gray-50">
              <td class="px-6 py-4 whitespace-nowrap text-gray-900">
                {{ new Date(trade.timestamp).toLocaleString() }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-gray-900">{{ trade.symbol }}</td>
              <td class="px-6 py-4 whitespace-nowrap">
                <span
                  class="px-2 py-1 text-xs rounded"
                  :class="trade.side === 'buy' ? 'bg-red-100 text-red-800' : 'bg-green-100 text-green-800'"
                >
                  {{ trade.side === 'buy' ? '买入' : '卖出' }}
                </span>
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-gray-900">
                ¥{{ trade.price?.toFixed(2) }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-gray-900">{{ trade.quantity }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-else class="mt-8 text-center py-12 text-gray-500">
      请先从回测配置页面运行回测
    </div>
  </div>
</template>

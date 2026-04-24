<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { backtestApi, default as api } from '../api'
import { useBacktestStore } from '../stores/backtest'
import { useNotificationStore } from '../stores/notification'
import { storeToRefs } from 'pinia'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, PieChart, BarChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
} from 'echarts/components'
import VChart from 'vue-echarts'
import KlineChart from '../components/KlineChart.vue'

use([
  CanvasRenderer,
  LineChart,
  PieChart,
  BarChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
])

const route = useRoute()
const router = useRouter()
const backtestStore = useBacktestStore()
const notificationStore = useNotificationStore()
const { loading, currentBacktest, trades } = storeToRefs(backtestStore)

const backtestId = computed(() => route.query.id)

const equityChartOption = computed(() => {
  if (!currentBacktest.value?.equity_curve) {
    return {}
  }

  try {
    const data = JSON.parse(currentBacktest.value.equity_curve)
    const dates = data.map((d) => d.date)
    const values = data.map((d) => d.value)
    const returns = data.map((d) => d.daily_return || 0)

    return {
      title: {
        text: '净值曲线',
        left: 'center',
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: {
          type: 'cross',
        },
        formatter: (params) => {
          const data = params[0]
          if (!data) return ''
          return `
            <div>日期: ${data.axisValue}</div>
            <div>净值: ${data.value?.toFixed(2) || '-'}</div>
          `
        },
      },
      legend: {
        data: ['净值', '日收益'],
        top: 30,
      },
      grid: {
        left: '3%',
        right: '4%',
        bottom: '3%',
        containLabel: true,
      },
      xAxis: {
        type: 'category',
        data: dates,
        boundaryGap: false,
      },
      yAxis: [
        {
          type: 'value',
          name: '净值',
          position: 'left',
        },
        {
          type: 'value',
          name: '日收益率',
          position: 'right',
          axisLabel: {
            formatter: (value) => (value * 100).toFixed(1) + '%',
          },
        },
      ],
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
        {
          name: '日收益',
          type: 'bar',
          yAxisIndex: 1,
          data: returns,
          itemStyle: {
            color: (params) => {
              return params.value >= 0 ? '#ef4444' : '#22c55e'
            },
          },
        },
      ],
    }
  } catch (e) {
    console.error('Failed to parse equity curve:', e)
    return {}
  }
})

const returnDistributionOption = computed(() => {
  if (trades.value.length === 0) {
    return {}
  }

  const profitable = trades.value.filter((t) => t.pnl && t.pnl > 0).length
  const loss = trades.value.filter((t) => t.pnl && t.pnl < 0).length

  return {
    title: {
      text: '盈亏交易分布',
      left: 'center',
    },
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} ({d}%)',
    },
    legend: {
      orient: 'vertical',
      left: 'left',
    },
    series: [
      {
        type: 'pie',
        radius: '50%',
        data: [
          { value: profitable, name: '盈利交易', itemStyle: { color: '#ef4444' } },
          { value: loss, name: '亏损交易', itemStyle: { color: '#22c55e' } },
        ],
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.5)',
          },
        },
      },
    ],
  }
})

const monthlyReturnOption = computed(() => {
  if (!currentBacktest.value?.monthly_returns) {
    return {}
  }

  try {
    const data = JSON.parse(currentBacktest.value.monthly_returns)
    return {
      title: {
        text: '月度收益',
        left: 'center',
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: {
          type: 'shadow',
        },
        formatter: (params) => {
          const data = params[0]
          if (!data) return ''
          return `
            <div>月份: ${data.axisValue}</div>
            <div>收益率: ${(data.value * 100).toFixed(2)}%</div>
          `
        },
      },
      xAxis: {
        type: 'category',
        data: data.map((d) => d.month),
      },
      yAxis: {
        type: 'value',
        axisLabel: {
          formatter: (value) => (value * 100).toFixed(0) + '%',
        },
      },
      series: [
        {
          type: 'bar',
          data: data.map((d) => d.return),
          itemStyle: {
            color: (params) => {
              return params.value >= 0 ? '#ef4444' : '#22c55e'
            },
          },
        },
      ],
    }
  } catch (e) {
    console.error('Failed to parse monthly returns:', e)
    return {}
  }
})

const fetchBacktest = async () => {
  if (!backtestId.value) {
    notificationStore.warning('未指定回测ID')
    return
  }

  try {
    await backtestStore.fetchBacktest(backtestApi, backtestId.value)
    await backtestStore.fetchTrades(backtestApi, backtestId.value)
    await fetchChartData(backtestId.value)
  } catch (error) {
    notificationStore.error('获取回测结果失败')
  }
}

const formatPercent = (value) => {
  if (value === null || value === undefined) return '-'
  return (value * 100).toFixed(2) + '%'
}

const formatCurrency = (value) => {
  if (value === null || value === undefined) return '-'
  return new Intl.NumberFormat('zh-CN', {
    style: 'currency',
    currency: 'CNY',
  }).format(value)
}

const runNewBacktest = () => {
  router.push('/backtest')
}

// --- K-line chart data from chart-data API ---
const chartData = ref(null)
const chartLoading = ref(false)
const chartError = ref(null)

const chartOhlcv = computed(() => chartData.value?.ohlcv || [])
const chartIndicators = computed(() => chartData.value?.indicators || [])
const chartTrades = computed(() => chartData.value?.trades || [])

const fetchChartData = async (id) => {
  if (!id) return
  chartLoading.value = true
  chartError.value = null
  try {
    const response = await api.get(`/backtests/${id}/chart-data`)
    chartData.value = response.data
  } catch (err) {
    console.error('Failed to fetch chart data:', err)
    chartError.value = err.response?.data?.detail || '获取图表数据失败'
  } finally {
    chartLoading.value = false
  }
}

watch(backtestId, (newId) => {
  if (newId) {
    fetchBacktest()
  }
}, { immediate: true })

onMounted(() => {
  if (!backtestId.value) {
    notificationStore.warning('未指定回测ID，请从回测配置页面进入')
  }
})
</script>

<template>
  <div class="p-4 sm:p-6 lg:p-8">
    <div class="flex flex-col sm:flex-row sm:justify-between sm:items-start gap-4">
      <div>
        <h1 class="text-3xl font-bold text-gray-900">回测结果</h1>
        <div class="flex items-center mt-2">
          <div class="h-[3px] w-12 rounded-full bg-gradient-to-r from-blue-500 to-blue-600 mr-3"></div>
          <p class="text-gray-500">查看策略回测的详细分析报告</p>
        </div>
      </div>
      <button
        @click="runNewBacktest"
        class="bg-gradient-to-r from-blue-600 to-blue-700 text-white px-5 py-2.5 rounded-lg hover:from-blue-700 hover:to-blue-800 shadow-sm transition-all self-start"
      >
        新建回测
      </button>
    </div>

    <div v-if="loading" class="mt-8 text-center py-12">
      <div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      <p class="mt-2 text-gray-600">加载中...</p>
    </div>

    <div v-else-if="currentBacktest">
      <div class="mt-6 bg-white rounded-xl shadow-sm border border-gray-100 p-4 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
        <div class="flex flex-wrap items-center gap-y-1">
          <span class="text-sm text-gray-600">标的: </span>
          <span class="font-medium mr-3">{{ currentBacktest.symbol }}</span>
          <span class="text-gray-300 hidden sm:inline mr-3">|</span>
          <span class="text-sm text-gray-600">期间: </span>
          <span class="font-medium mr-3">{{ currentBacktest.start_date }} 至 {{ currentBacktest.end_date }}</span>
          <span class="text-gray-300 hidden sm:inline mr-3">|</span>
          <span class="text-sm text-gray-600">初始资金: </span>
          <span class="font-medium">{{ formatCurrency(currentBacktest.initial_capital) }}</span>
        </div>
        <div
          class="px-3 py-1 rounded-full text-sm font-medium"
          :class="currentBacktest.status === 'completed' ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'"
        >
          {{ currentBacktest.status === 'completed' ? '已完成' : '运行中' }}
        </div>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mt-8">
        <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-6 border-l-4 hover:shadow-md transition-shadow duration-200" :class="currentBacktest.total_return >= 0 ? 'border-l-red-500' : 'border-l-green-500'">
          <p class="text-sm text-gray-500">总收益率</p>
          <p
            class="text-3xl font-bold mt-2"
            :class="currentBacktest.total_return >= 0 ? 'text-red-600' : 'text-green-600'"
          >
            {{ formatPercent(currentBacktest.total_return) }}
          </p>
        </div>
        <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-6 border-l-4 border-l-blue-500 hover:shadow-md transition-shadow duration-200">
          <p class="text-sm text-gray-500">年化收益</p>
          <p
            class="text-3xl font-bold mt-2"
            :class="currentBacktest.annual_return >= 0 ? 'text-red-600' : 'text-green-600'"
          >
            {{ formatPercent(currentBacktest.annual_return) }}
          </p>
        </div>
        <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-6 border-l-4 border-l-violet-500 hover:shadow-md transition-shadow duration-200">
          <p class="text-sm text-gray-500">夏普比率</p>
          <p class="text-3xl font-bold mt-2 text-violet-600">
            {{ currentBacktest.sharpe_ratio?.toFixed(2) || '-' }}
          </p>
        </div>
        <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-6 border-l-4 border-l-green-500 hover:shadow-md transition-shadow duration-200">
          <p class="text-sm text-gray-500">最大回撤</p>
          <p class="text-3xl font-bold mt-2 text-green-600">
            {{ formatPercent(currentBacktest.max_drawdown) }}
          </p>
        </div>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mt-6">
        <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-6 hover:shadow-md transition-shadow duration-200">
          <p class="text-sm text-gray-500">胜率</p>
          <p class="text-xl font-bold mt-2 text-blue-600">
            {{ formatPercent(currentBacktest.win_rate) }}
          </p>
        </div>
        <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-6 hover:shadow-md transition-shadow duration-200">
          <p class="text-sm text-gray-500">交易次数</p>
          <p class="text-xl font-bold mt-2 text-gray-900">
            {{ trades.length }}
          </p>
        </div>
        <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-6 hover:shadow-md transition-shadow duration-200">
          <p class="text-sm text-gray-500">最终资产</p>
          <p class="text-xl font-bold mt-2 text-gray-900">
            {{ formatCurrency(currentBacktest.initial_capital * (1 + (currentBacktest.total_return || 0))) }}
          </p>
        </div>
        <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-6 hover:shadow-md transition-shadow duration-200">
          <p class="text-sm text-gray-500">回测时间</p>
          <p class="text-sm font-medium mt-2 text-gray-700">
            {{ new Date(currentBacktest.created_at).toLocaleString('zh-CN') }}
          </p>
        </div>
      </div>

      <div class="mt-8">
        <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
          <h2 class="text-lg font-semibold mb-4">K线图表</h2>
          <div v-if="chartLoading" class="text-center py-8">
            <div class="inline-block animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
            <p class="mt-2 text-gray-500 text-sm">加载图表数据...</p>
          </div>
          <div v-else-if="chartError" class="text-center py-8 text-gray-500 text-sm">
            {{ chartError }}
          </div>
          <KlineChart
            v-else-if="chartOhlcv.length > 0"
            :data="chartOhlcv"
            :indicators="chartIndicators"
            :trades="chartTrades"
            height="560px"
          />
          <div v-else class="text-center py-8 text-gray-500 text-sm">
            暂无K线图表数据
          </div>
        </div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-8 mt-8">
        <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-6 min-h-[384px]">
          <v-chart class="h-96" :option="equityChartOption" autoresize />
        </div>

        <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-6 min-h-[384px]">
          <v-chart class="h-96" :option="returnDistributionOption" autoresize />
        </div>
      </div>

      <div v-if="currentBacktest.monthly_returns" class="mt-8 bg-white rounded-xl shadow-sm border border-gray-100 p-6 min-h-[320px]">
        <v-chart class="h-80" :option="monthlyReturnOption" autoresize />
      </div>

      <div class="mt-8 bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        <div class="px-6 py-4 border-b border-gray-100 flex justify-between items-center">
          <h2 class="text-lg font-semibold">交易明细</h2>
          <span class="text-sm text-gray-500">{{ trades.length }} 笔交易</span>
        </div>
        <div class="overflow-x-auto">
          <table class="min-w-full">
            <thead class="bg-gray-50">
              <tr>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">序号</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">时间</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">标的</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">方向</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">价格</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">数量</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">手续费</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">盈亏</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-200 bg-white">
              <tr v-if="trades.length === 0">
                <td colspan="8" class="px-6 py-8 text-center text-gray-500">暂无交易记录</td>
              </tr>
              <tr v-else v-for="(trade, index) in trades" :key="trade.id" class="hover:bg-gray-50 transition-colors">
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                  {{ index + 1 }}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                  {{ new Date(trade.timestamp).toLocaleString('zh-CN') }}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                  {{ trade.symbol }}
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                  <span
                    class="px-2 py-1 text-xs rounded font-medium"
                    :class="trade.side === 'buy' ? 'bg-red-100 text-red-800' : 'bg-green-100 text-green-800'"
                  >
                    {{ trade.side === 'buy' ? '买入' : '卖出' }}
                  </span>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                  {{ trade.price?.toFixed(2) }}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                  {{ trade.quantity }}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {{ trade.commission != null ? formatCurrency(trade.commission) : '-' }}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium" :class="trade.pnl > 0 ? 'text-red-600' : trade.pnl < 0 ? 'text-green-600' : 'text-gray-400'">
                  {{ trade.pnl != null ? formatCurrency(trade.pnl) : '-' }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <div v-else class="mt-8 text-center py-16 bg-white rounded-xl shadow-sm border border-gray-100">
      <svg class="mx-auto h-16 w-16 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
      </svg>
      <h3 class="mt-4 text-lg font-medium text-gray-900">暂无回测结果</h3>
      <p class="mt-2 text-gray-500">请先从回测配置页面运行回测</p>
      <button
        @click="runNewBacktest"
        class="mt-6 bg-gradient-to-r from-blue-600 to-blue-700 text-white px-5 py-2.5 rounded-lg hover:from-blue-700 hover:to-blue-800 shadow-sm transition-all"
      >
        去运行回测
      </button>
    </div>
  </div>
</template>

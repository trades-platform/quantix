<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { backtestApi } from '../api'
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

  const profitable = trades.value.filter((t) => t.profit && t.profit > 0).length
  const loss = trades.value.filter((t) => t.profit && t.profit < 0).length

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
  <div class="p-8">
    <div class="flex justify-between items-start">
      <div>
        <h1 class="text-3xl font-bold text-gray-900">回测结果</h1>
        <p class="mt-2 text-gray-600">查看策略回测的详细分析报告</p>
      </div>
      <button
        @click="runNewBacktest"
        class="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
      >
        新建回测
      </button>
    </div>

    <div v-if="loading" class="mt-8 text-center py-12">
      <div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      <p class="mt-2 text-gray-600">加载中...</p>
    </div>

    <div v-else-if="currentBacktest">
      <div class="mt-6 bg-gray-50 rounded-lg p-4 flex justify-between items-center">
        <div>
          <span class="text-sm text-gray-600">标的: </span>
          <span class="font-medium">{{ currentBacktest.symbol }}</span>
          <span class="mx-3 text-gray-300">|</span>
          <span class="text-sm text-gray-600">期间: </span>
          <span class="font-medium">{{ currentBacktest.start_date }} 至 {{ currentBacktest.end_date }}</span>
          <span class="mx-3 text-gray-300">|</span>
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
        <div class="bg-white rounded-lg shadow p-6 border-l-4" :class="currentBacktest.total_return >= 0 ? 'border-red-500' : 'border-green-500'">
          <p class="text-sm text-gray-600">总收益率</p>
          <p
            class="text-3xl font-bold mt-2"
            :class="currentBacktest.total_return >= 0 ? 'text-red-600' : 'text-green-600'"
          >
            {{ formatPercent(currentBacktest.total_return) }}
          </p>
        </div>
        <div class="bg-white rounded-lg shadow p-6 border-l-4 border-blue-500">
          <p class="text-sm text-gray-600">年化收益</p>
          <p
            class="text-3xl font-bold mt-2"
            :class="currentBacktest.annual_return >= 0 ? 'text-red-600' : 'text-green-600'"
          >
            {{ formatPercent(currentBacktest.annual_return) }}
          </p>
        </div>
        <div class="bg-white rounded-lg shadow p-6 border-l-4 border-purple-500">
          <p class="text-sm text-gray-600">夏普比率</p>
          <p class="text-3xl font-bold mt-2 text-purple-600">
            {{ currentBacktest.sharpe_ratio?.toFixed(2) || '-' }}
          </p>
        </div>
        <div class="bg-white rounded-lg shadow p-6 border-l-4 border-green-500">
          <p class="text-sm text-gray-600">最大回撤</p>
          <p class="text-3xl font-bold mt-2 text-green-600">
            {{ formatPercent(currentBacktest.max_drawdown) }}
          </p>
        </div>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mt-6">
        <div class="bg-white rounded-lg shadow p-6">
          <p class="text-sm text-gray-600">胜率</p>
          <p class="text-xl font-bold mt-2 text-blue-600">
            {{ formatPercent(currentBacktest.win_rate) }}
          </p>
        </div>
        <div class="bg-white rounded-lg shadow p-6">
          <p class="text-sm text-gray-600">交易次数</p>
          <p class="text-xl font-bold mt-2 text-gray-900">
            {{ trades.length }}
          </p>
        </div>
        <div class="bg-white rounded-lg shadow p-6">
          <p class="text-sm text-gray-600">最终资产</p>
          <p class="text-xl font-bold mt-2 text-gray-900">
            {{ formatCurrency(currentBacktest.initial_capital * (1 + (currentBacktest.total_return || 0))) }}
          </p>
        </div>
        <div class="bg-white rounded-lg shadow p-6">
          <p class="text-sm text-gray-600">回测时间</p>
          <p class="text-sm font-medium mt-2 text-gray-700">
            {{ new Date(currentBacktest.created_at).toLocaleString('zh-CN') }}
          </p>
        </div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-8 mt-8">
        <div class="bg-white rounded-lg shadow p-6">
          <v-chart class="h-96" :option="equityChartOption" autoresize />
        </div>

        <div class="bg-white rounded-lg shadow p-6">
          <v-chart class="h-96" :option="returnDistributionOption" autoresize />
        </div>
      </div>

      <div v-if="currentBacktest.monthly_returns" class="mt-8 bg-white rounded-lg shadow p-6">
        <v-chart class="h-80" :option="monthlyReturnOption" autoresize />
      </div>

      <div class="mt-8 bg-white rounded-lg shadow overflow-hidden">
        <div class="px-6 py-4 border-b flex justify-between items-center">
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
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">盈亏</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-200 bg-white">
              <tr v-if="trades.length === 0">
                <td colspan="7" class="px-6 py-8 text-center text-gray-500">暂无交易记录</td>
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
                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium" :class="trade.profit >= 0 ? 'text-red-600' : 'text-green-600'">
                  {{ trade.profit !== undefined && trade.profit !== null ? formatCurrency(trade.profit) : '-' }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <div v-else class="mt-8 text-center py-16 bg-white rounded-lg shadow">
      <svg class="mx-auto h-16 w-16 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
      </svg>
      <h3 class="mt-4 text-lg font-medium text-gray-900">暂无回测结果</h3>
      <p class="mt-2 text-gray-600">请先从回测配置页面运行回测</p>
      <button
        @click="runNewBacktest"
        class="mt-4 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
      >
        去运行回测
      </button>
    </div>
  </div>
</template>

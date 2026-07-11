<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { dataApi } from '../api'
import { useDataStore } from '../stores/data'
import { useNotificationStore } from '../stores/notification'
import { storeToRefs } from 'pinia'
import KlineChart from '../components/KlineChart.vue'

const dataStore = useDataStore()
const { symbols, klineData, chartIndicators, loading, selectedSymbol, hasData } = storeToRefs(dataStore)
const notificationStore = useNotificationStore()

const klineLoading = ref(false)
const klineStats = ref(null)

const searchQuery = ref('')

// Chart filter state
const chartFilter = ref({
  period: '1D',
  adjust: 'qfq',
  startDate: '',
  endDate: '',
})
const activeIndicators = ref(new Set(['ma', 'volume']))
const selectedMaPeriods = ref([5, 20])
const isFullscreen = ref(false)

// --- Settings persistence ---
const SETTINGS_KEY = 'quantix:chartSettings'
const showSettingsPanel = ref(false)

const loadSettings = () => {
  try {
    const raw = localStorage.getItem(SETTINGS_KEY)
    if (!raw) return
    const parsed = JSON.parse(raw)
    if (parsed.chartFilter) {
      chartFilter.value = { ...chartFilter.value, ...parsed.chartFilter }
    }
    if (parsed.activeIndicators) {
      activeIndicators.value = new Set(parsed.activeIndicators)
    }
    if (parsed.selectedMaPeriods) {
      selectedMaPeriods.value = parsed.selectedMaPeriods
    }
    if (parsed.maColors) {
      maColors.value = { ...maColors.value, ...parsed.maColors }
    }
  } catch (e) {
    console.error('Failed to load chart settings', e)
  }
}

const saveSettings = () => {
  try {
    const payload = {
      chartFilter: {
        period: chartFilter.value.period,
        adjust: chartFilter.value.adjust,
      },
      activeIndicators: Array.from(activeIndicators.value),
      selectedMaPeriods: selectedMaPeriods.value,
      maColors: maColors.value,
    }
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(payload))
  } catch (e) {
    console.error('Failed to save chart settings', e)
  }
}

const openSettings = () => {
  showSettingsPanel.value = true
}

const closeSettings = () => {
  showSettingsPanel.value = false
}

const confirmSettings = () => {
  saveSettings()
  showSettingsPanel.value = false
}


const periodOptions = [
  { value: '1min', label: '1分钟' },
  { value: '5min', label: '5分钟' },
  { value: '15min', label: '15分钟' },
  { value: '30min', label: '30分钟' },
  { value: '60min', label: '60分钟' },
  { value: '120min', label: '120分钟' },
  { value: '1D', label: '日线' },
  { value: '1W', label: '周线' },
  { value: '1M', label: '月线' },
  { value: '1Q', label: '季线' },
]
const adjustOptions = [
  { value: 'none', label: '不复权' },
  { value: 'hfq', label: '后复权' },
  { value: 'qfq', label: '前复权' },
]
const indicatorOptions = [
  { key: 'boll', label: 'BOLL' },
  { key: 'macd', label: 'MACD' },
  { key: 'rsi', label: 'RSI' },
  { key: 'kdj', label: 'KDJ' },
  { key: 'atr', label: 'ATR' },
  { key: 'volume', label: 'Volume' },
]
const maPeriodOptions = [5, 10, 20, 60, 120, 250]
const maColors = ref({
  5: '#F59E0B',
  10: '#3B82F6',
  20: '#8B5CF6',
  60: '#EC4899',
  120: '#14B8A6',
  250: '#F97316',
})

// Build layer specs from active indicators
const buildLayers = () => {
  const layers = []
  const active = activeIndicators.value

  if (active.has('ma') && selectedMaPeriods.value.length > 0) {
    for (const period of selectedMaPeriods.value) {
      layers.push({
        indicator: 'ma',
        name: `MA(${period})`,
        params: { period },
        color: maColors.value[period] || '#999',
      })
    }
  }
  if (active.has('boll')) {
    layers.push({ indicator: 'boll', name: 'BOLL(20,2)', params: { period: 20, std_dev: 2.0 } })
  }
  if (active.has('macd')) {
    layers.push({ indicator: 'macd', name: 'MACD(12,26,9)', params: { fast: 12, slow: 26, signal: 9 } })
  }
  if (active.has('rsi')) {
    layers.push({ indicator: 'rsi', name: 'RSI(14)', params: { period: 14 } })
  }
  if (active.has('kdj')) {
    layers.push({ indicator: 'kdj', name: 'KDJ(9,3,3)', params: { n: 9, m1: 3, m2: 3 } })
  }
  if (active.has('atr')) {
    layers.push({ indicator: 'atr', name: 'ATR(14)', params: { period: 14 } })
  }
  if (active.has('volume')) {
    layers.push({ indicator: 'volume', name: 'Volume', pane: 'volume' })
  }
  return layers
}

// Fetch form state
const showFetchDialog = ref(false)
const fetchForm = ref({
  symbol: '',
  period: 'min1',
  startDate: '',
  endDate: ''
})
const fetching = ref(false)

// Batch fetch form state
const showBatchFetchDialog = ref(false)
const batchFetchForm = ref({
  symbols: '',
  period: 'min1',
  startDate: '',
  endDate: ''
})
const batchFetching = ref(false)
const batchFetchResults = ref([])

// Delete state
const showDeleteDialog = ref(false)
const deletingSymbol = ref(null)
const deleting = ref(false)

const confirmDeleteSymbol = (symbol) => {
  deletingSymbol.value = symbol
  showDeleteDialog.value = true
}

const handleDeleteSymbol = async () => {
  if (!deletingSymbol.value) return
  deleting.value = true
  try {
    await dataStore.deleteSymbol(dataApi, deletingSymbol.value)
    notificationStore.success(`已删除 ${deletingSymbol.value}`)
    showDeleteDialog.value = false
    deletingSymbol.value = null
  } catch (error) {
    notificationStore.error('删除失败: ' + error.response?.data?.detail || error.message)
  } finally {
    deleting.value = false
  }
}

const filteredSymbols = computed(() => {
  if (!searchQuery.value) return symbols.value
  const query = searchQuery.value.toLowerCase()
  return symbols.value.filter((s) => {
    const symbol = typeof s === 'string' ? s : s.symbol
    const name = typeof s === 'string' ? '' : (s.name || '')
    return symbol.toLowerCase().includes(query) || name.toLowerCase().includes(query)
  })
})

const fetchSymbols = async () => {
  try {
    await dataStore.fetchSymbols(dataApi)
  } catch (error) {
    notificationStore.error('获取标的列表失败')
  }
}

const fetchChartData = async () => {
  if (!selectedSymbol.value) return

  klineLoading.value = true
  try {
    const layers = buildLayers()
    const params = {
      symbol: selectedSymbol.value,
      period: chartFilter.value.period,
      adjust: chartFilter.value.adjust,
      layers: layers.length > 0 ? layers : undefined,
    }
    if (chartFilter.value.startDate) params.start_date = chartFilter.value.startDate
    if (chartFilter.value.endDate) params.end_date = chartFilter.value.endDate

    await dataStore.fetchChartData(dataApi, params)
    calculateStats()
  } catch (error) {
    notificationStore.error('获取图表数据失败')
  } finally {
    klineLoading.value = false
  }
}

const calculateStats = () => {
  if (klineData.value.length === 0) {
    klineStats.value = null
    return
  }

  const data = klineData.value
  const first = data[0]
  const last = data[data.length - 1]

  const totalReturn = ((last.close - first.close) / first.close) * 100

  klineStats.value = {
    dataPoints: data.length,
    dateRange: `${first.timestamp.split('T')[0]} 至 ${last.timestamp.split('T')[0]}`,
    totalReturn: totalReturn.toFixed(2),
    high: data.reduce((max, d) => d.high > max ? d.high : max, -Infinity).toFixed(2),
    low: data.reduce((min, d) => d.low < min ? d.low : min, Infinity).toFixed(2),
    avgVolume: Math.round(data.reduce((sum, d) => sum + d.volume, 0) / data.length).toLocaleString(),
  }
}

const toLocalDateStr = (date) => {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

const openFetchDialog = () => {
  const today = new Date()
  fetchForm.value = {
    symbol: '',
    period: 'min1',
    startDate: '1970-01-01',
    endDate: toLocalDateStr(today)
  }
  showFetchDialog.value = true
}

const handleFetchKline = async () => {
  if (!fetchForm.value.symbol.trim()) {
    notificationStore.warning('请输入标的代码')
    return
  }

  fetching.value = true
  try {
    const result = await dataStore.fetchSingleKline(dataApi, {
      symbol: fetchForm.value.symbol,
      period: fetchForm.value.period,
      start_date: fetchForm.value.startDate,
      end_date: fetchForm.value.endDate
    })
    if (result.count > 0) {
      notificationStore.success(`数据获取成功，共获取 ${result.count} 条数据`)
      showFetchDialog.value = false
      await fetchSymbols()
    } else {
      notificationStore.warning(`未获取到数据，请检查标的代码和日期范围是否正确`)
    }
  } catch (error) {
    notificationStore.error('获取数据失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    fetching.value = false
  }
}

const openBatchFetchDialog = () => {
  const today = new Date()
  batchFetchForm.value = {
    symbols: '',
    period: 'min1',
    startDate: '1970-01-01',
    endDate: toLocalDateStr(today)
  }
  batchFetchResults.value = []
  showBatchFetchDialog.value = true
}

const handleBatchFetchKline = async () => {
  const symbolsText = batchFetchForm.value.symbols.trim()
  if (!symbolsText) {
    notificationStore.warning('请输入标的代码')
    return
  }

  const syms = symbolsText.split(/[\n,]+/).map(s => s.trim()).filter(s => s)
  if (syms.length === 0) {
    notificationStore.warning('请输入有效的标的代码')
    return
  }

  batchFetching.value = true
  try {
    const result = await dataStore.fetchBatchKline(dataApi, {
      symbols: syms,
      period: batchFetchForm.value.period,
      start_date: batchFetchForm.value.startDate,
      end_date: batchFetchForm.value.endDate
    })
    batchFetchResults.value = result.results || []
    const errors = result.errors || []
    if (errors.length > 0) {
      notificationStore.warning(`批量获取完成，${result.success} 个成功，${result.failed} 个失败`)
    } else {
      const totalCount = batchFetchResults.value.reduce((sum, r) => sum + r.count, 0)
      notificationStore.success(`批量获取完成，共获取 ${totalCount} 条数据`)
    }
    await fetchSymbols()
  } catch (error) {
    notificationStore.error('批量获取失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    batchFetching.value = false
  }
}

const selectSymbol = (symbol) => {
  selectedSymbol.value = symbol
  fetchChartData()
}

const toggleIndicator = (key) => {
  const s = new Set(activeIndicators.value)
  if (s.has(key)) {
    s.delete(key)
  } else {
    s.add(key)
  }
  activeIndicators.value = s
  if (selectedSymbol.value) {
    fetchChartData()
  }
}

const toggleMaPeriod = (period) => {
  const idx = selectedMaPeriods.value.indexOf(period)
  if (idx >= 0) {
    selectedMaPeriods.value = selectedMaPeriods.value.filter(p => p !== period)
  } else {
    selectedMaPeriods.value = [...selectedMaPeriods.value, period].sort((a, b) => a - b)
  }
  if (selectedMaPeriods.value.length === 0) {
    const s = new Set(activeIndicators.value)
    s.delete('ma')
    activeIndicators.value = s
  } else {
    const s = new Set(activeIndicators.value)
    s.add('ma')
    activeIndicators.value = s
  }
  if (selectedSymbol.value) {
    fetchChartData()
  }
}

const toggleFullscreen = () => {
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen().catch(() => {})
    isFullscreen.value = true
  } else {
    document.exitFullscreen()
    isFullscreen.value = false
  }
}

const onFullscreenChange = () => {
  isFullscreen.value = !!document.fullscreenElement
}

onMounted(() => {
  document.addEventListener('fullscreenchange', onFullscreenChange)
  loadSettings()
  fetchSymbols()
})

onUnmounted(() => {
  document.removeEventListener('fullscreenchange', onFullscreenChange)
})

watch(selectedSymbol, () => {
  if (selectedSymbol.value) {
    fetchChartData()
  }
})

watch(() => chartFilter.value.period, saveSettings)
watch(() => chartFilter.value.adjust, saveSettings)
watch(activeIndicators, saveSettings, { deep: true })
watch(selectedMaPeriods, saveSettings, { deep: true })
</script>

<template>
  <div class="p-4 sm:p-6 lg:p-8 flex flex-col h-[calc(100dvh-4rem)] overflow-hidden">
    <div class="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-4 mb-6 shrink-0">
      <div>
        <h1 class="text-3xl font-bold text-gray-900">数据管理</h1>
        <div class="flex items-center mt-2">
          <div class="h-[3px] w-12 rounded-full bg-gradient-to-r from-blue-500 to-blue-600 mr-3"></div>
          <p class="text-gray-500">管理K线数据和查看行情信息</p>
        </div>
      </div>
      <div class="flex space-x-3">
        <button
          @click="openFetchDialog"
          class="bg-gradient-to-r from-emerald-600 to-emerald-700 text-white px-5 py-2.5 rounded-lg hover:from-emerald-700 hover:to-emerald-800 flex items-center shadow-sm transition-all"
        >
          <svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          获取数据
        </button>
        <button
          @click="openBatchFetchDialog"
          class="bg-gradient-to-r from-violet-600 to-violet-700 text-white px-5 py-2.5 rounded-lg hover:from-violet-700 hover:to-violet-800 flex items-center shadow-sm transition-all"
        >
          <svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
          </svg>
          批量获取
        </button>
      </div>
    </div>

    <div class="flex-1 min-h-0 grid grid-cols-1 lg:grid-cols-3 gap-8">
      <div class="lg:col-span-1 h-full overflow-hidden">
        <div class="bg-white rounded-xl shadow-sm border border-gray-100 h-full flex flex-col">
          <div class="p-4 border-b shrink-0">
            <div class="flex space-x-2">
              <input
                v-model="searchQuery"
                type="text"
                placeholder="搜索标的代码或名称..."
                class="flex-1 px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-gray-50 focus:bg-white transition-all"
              />
              <button
                @click="fetchSymbols"
                :disabled="loading"
                class="px-3 py-2 border rounded-lg hover:bg-gray-50 disabled:opacity-50 transition-colors"
                title="刷新列表"
              >
                <svg :class="{ 'animate-spin': loading }" class="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
              </button>
            </div>
          </div>

          <div class="flex-1 overflow-auto min-h-0">
            <div v-if="loading" class="p-8 text-center text-gray-500">
              <div class="inline-block animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
              <p class="mt-2">加载中...</p>
            </div>
            <div v-else-if="filteredSymbols.length === 0" class="p-8 text-center text-gray-500">
              <svg class="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
              </svg>
              <p class="mt-2 text-sm">{{ searchQuery ? '未找到匹配的标的' : '暂无数据' }}</p>
            </div>
            <div v-else>
              <table class="min-w-full">
                <thead class="bg-gray-50 sticky top-0">
                  <tr>
                    <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">标的</th>
                    <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">名称</th>
                    <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">类型</th>
                    <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">起始时间</th>
                    <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">结束时间</th>
                    <th class="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">数据量</th>
                    <th class="px-4 py-2 text-center text-xs font-medium text-gray-500 uppercase">操作</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-gray-200 bg-white">
                  <tr
                    v-for="item in filteredSymbols"
                    :key="typeof item === 'string' ? item : item.symbol"
                    @click="selectSymbol(typeof item === 'string' ? item : item.symbol)"
                    class="hover:bg-gray-50 cursor-pointer transition-colors"
                    :class="{ 'bg-blue-50': selectedSymbol === (typeof item === 'string' ? item : item.symbol) }"
                  >
                    <td class="px-4 py-3 whitespace-nowrap">
                      <div class="font-medium text-gray-900">{{ typeof item === 'string' ? item : item.symbol }}</div>
                    </td>
                    <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-600">
                      {{ typeof item === 'string' ? '-' : (item.name || '-') }}
                    </td>
                    <td class="px-4 py-3 whitespace-nowrap text-sm">
                      <span class="px-2 py-1 text-xs rounded" :class="{
                        'bg-blue-100 text-blue-800': (typeof item === 'string' ? 'stock' : item.data_type) === 'stock',
                        'bg-green-100 text-green-800': (typeof item === 'string' ? 'stock' : item.data_type) === 'index',
                        'bg-purple-100 text-purple-800': (typeof item === 'string' ? 'stock' : item.data_type) === 'fund'
                      }">
                        {{ typeof item === 'string' ? '股票' : (item.data_type === 'stock' ? '股票' : item.data_type === 'index' ? '指数' : item.data_type === 'fund' ? '基金' : item.data_type) }}
                      </span>
                    </td>
                    <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-600">
                      {{ typeof item === 'string' ? '-' : (item.earliest_timestamp ? item.earliest_timestamp.split('T')[0] : '-') }}
                    </td>
                    <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-600">
                      {{ typeof item === 'string' ? '-' : (item.latest_timestamp ? item.latest_timestamp.split('T')[0] : '-') }}
                    </td>
                    <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-600 text-right">
                      {{ typeof item === 'string' ? '-' : (item.row_count?.toLocaleString() || '-') }}
                    </td>
                    <td class="px-4 py-3 whitespace-nowrap text-center">
                      <button
                        @click.stop="confirmDeleteSymbol(typeof item === 'string' ? item : item.symbol)"
                        class="p-1.5 rounded-lg text-gray-400 hover:text-red-600 hover:bg-red-50 transition-colors"
                        title="删除标的"
                      >
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <div class="p-4 border-t bg-gray-50 shrink-0">
            <div class="flex justify-between text-sm">
              <span class="text-gray-600">总计:</span>
              <span class="font-medium">{{ symbols.length }} 个标的</span>
            </div>
          </div>
        </div>
      </div>

      <div class="lg:col-span-2 h-full overflow-hidden">
        <div v-if="!selectedSymbol" class="bg-white rounded-xl shadow-sm border border-gray-100 p-12 text-center h-full flex items-center justify-center">
          <svg class="mx-auto h-16 w-16 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
          <h3 class="mt-4 text-lg font-medium text-gray-900">请选择标的</h3>
          <p class="mt-2 text-gray-500">从左侧列表选择一个标的查看K线数据</p>
        </div>

        <div v-else class="h-full flex flex-col overflow-hidden">
          <div v-if="klineStats" class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4 shrink-0">
            <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-4">
              <p class="text-xs text-gray-500">数据点数</p>
              <p class="text-lg font-bold mt-1 text-gray-900">{{ klineStats.dataPoints }}</p>
            </div>
            <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-4">
              <p class="text-xs text-gray-500">区间收益</p>
              <p class="text-lg font-bold mt-1" :class="parseFloat(klineStats.totalReturn) >= 0 ? 'text-red-600' : 'text-green-600'">
                {{ klineStats.totalReturn }}%
              </p>
            </div>
            <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-4">
              <p class="text-xs text-gray-500">最高价</p>
              <p class="text-lg font-bold mt-1 text-red-600">{{ klineStats.high }}</p>
            </div>
            <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-4">
              <p class="text-xs text-gray-500">最低价</p>
              <p class="text-lg font-bold mt-1 text-green-600">{{ klineStats.low }}</p>
            </div>
          </div>

          <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-4 flex-1 flex flex-col min-h-0 overflow-hidden" :class="{ 'fixed inset-0 z-50 rounded-none p-4': isFullscreen }">
            <!-- Chart control bar row 1: period / adjust / date range / renderer -->
            <div class="flex flex-wrap items-center gap-3 mb-2 shrink-0">
              <select
                v-model="chartFilter.period"
                @change="fetchChartData"
                class="px-3 py-1.5 border rounded-lg text-sm bg-gray-50 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 focus:bg-white"
              >
                <option v-for="opt in periodOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
              </select>

              <select
                v-model="chartFilter.adjust"
                @change="fetchChartData"
                class="px-3 py-1.5 border rounded-lg text-sm bg-gray-50 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 focus:bg-white"
              >
                <option v-for="opt in adjustOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
              </select>

              <input
                v-model="chartFilter.startDate"
                type="date"
                placeholder="开始日期"
                class="px-3 py-1.5 border rounded-lg text-sm bg-gray-50 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 focus:bg-white"
                @change="fetchChartData"
              />
              <span class="text-gray-400 text-sm">至</span>
              <input
                v-model="chartFilter.endDate"
                type="date"
                placeholder="结束日期"
                class="px-3 py-1.5 border rounded-lg text-sm bg-gray-50 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 focus:bg-white"
                @change="fetchChartData"
              />

              <button
                @click="fetchChartData"
                :disabled="klineLoading"
                class="px-4 py-1.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
              >
                查询
              </button>
            </div>

            <!-- Chart control bar row 2: settings button + active summary -->
            <div class="flex flex-wrap items-center gap-2 mb-2 shrink-0">
              <button
                @click="openSettings"
                class="px-3 py-1.5 text-sm rounded-lg border border-gray-300 hover:border-gray-400 hover:bg-gray-50 transition-all flex items-center gap-1.5"
                title="图表设置"
              >
                <svg class="w-4 h-4 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
                设置
              </button>

              <span v-if="selectedMaPeriods.length > 0" class="text-xs text-gray-500">
                MA:
                <span
                  v-for="p in selectedMaPeriods"
                  :key="p"
                  class="inline-block w-2 h-2 rounded-full mx-0.5"
                  :style="{ backgroundColor: maColors[p] }"
                />
              </span>

              <span v-if="activeIndicators.size > 0" class="text-xs text-gray-500">
                指标:
                <span
                  v-for="ind in indicatorOptions.filter(i => activeIndicators.has(i.key))"
                  :key="ind.key"
                  class="inline-flex items-center px-1.5 py-0.5 rounded bg-blue-50 text-blue-700 text-[10px] mx-0.5"
                >
                  {{ ind.label }}
                </span>
              </span>
            </div>

            <div v-if="klineStats" class="flex items-center justify-between mb-2 shrink-0">
              <span class="text-sm text-gray-500">{{ selectedSymbol }} · {{ klineStats.dateRange }} · {{ klineStats.dataPoints }} bars</span>
              <button
                @click="toggleFullscreen"
                class="p-1.5 rounded-lg hover:bg-gray-100 transition-colors text-gray-400 hover:text-gray-600"
                :title="isFullscreen ? '退出全屏' : '全屏显示'"
              >
                <svg v-if="!isFullscreen" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 8V4m0 0h4m10 10V4m0 0h-4m1 10H3a1 1 0 01-1-1V3a1 1 0 011-1h1m14 10a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h2m10 10V17" />
                </svg>
                <svg v-else class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 9V4.5M9 9H4.5M9 14L4.5 19M9 14h4.5M15 9h4.5M15 9V4.5M15 14l4.5 5M15 14h4.5" />
                </svg>
              </button>
            </div>

            <KlineChart v-if="hasData && !klineLoading" :data="klineData" :indicators="chartIndicators" :height="isFullscreen ? 'calc(100vh - 180px)' : '100%'" :dark-mode="false" class="flex-1 min-h-0" />
            <div v-else-if="klineLoading" class="flex-1 flex items-center justify-center text-gray-500 min-h-0">
              <div class="inline-block animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
              <span class="ml-2">加载中...</span>
            </div>
            <div v-else class="flex-1 flex items-center justify-center text-gray-500 min-h-0">
              暂无K线数据
            </div>
          </div>

        </div>
      </div>
    </div>

    <Teleport to="body">
      <div
        v-if="showFetchDialog"
        class="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4"
        @click.self="showFetchDialog = false"
      >
        <div class="bg-white rounded-xl shadow-xl w-full max-w-md overflow-hidden">
          <div class="px-6 py-4 border-b flex justify-between items-center">
            <h2 class="text-xl font-semibold">获取K线数据</h2>
            <button
              @click="showFetchDialog = false"
              class="text-gray-400 hover:text-gray-600 transition-colors"
            >
              <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <div class="p-6 space-y-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">标的代码 <span class="text-red-500">*</span></label>
              <input
                v-model="fetchForm.symbol"
                type="text"
                class="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 bg-gray-50 focus:bg-white transition-all"
                placeholder="例如: 600000.SH"
              />
            </div>

            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">开始日期</label>
              <input
                v-model="fetchForm.startDate"
                type="date"
                class="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 bg-gray-50 focus:bg-white transition-all"
              />
            </div>

            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">结束日期</label>
              <input
                v-model="fetchForm.endDate"
                type="date"
                class="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 bg-gray-50 focus:bg-white transition-all"
              />
            </div>
          </div>

          <div class="px-6 py-4 bg-gray-50 flex justify-end space-x-3">
            <button
              @click="showFetchDialog = false"
              :disabled="fetching"
              class="px-4 py-2 border rounded-lg hover:bg-gray-100 disabled:opacity-50 transition-colors"
            >
              取消
            </button>
            <button
              @click="handleFetchKline"
              :disabled="fetching"
              class="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed flex items-center transition-colors"
            >
              <svg v-if="fetching" class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              {{ fetching ? '获取中...' : '获取' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div
        v-if="showBatchFetchDialog"
        class="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4"
        @click.self="showBatchFetchDialog = false"
      >
        <div class="bg-white rounded-xl shadow-xl w-full max-w-lg overflow-hidden">
          <div class="px-6 py-4 border-b flex justify-between items-center">
            <h2 class="text-xl font-semibold">批量获取K线数据</h2>
            <button
              @click="showBatchFetchDialog = false"
              class="text-gray-400 hover:text-gray-600 transition-colors"
            >
              <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <div class="p-6 space-y-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">标的代码 <span class="text-red-500">*</span></label>
              <textarea
                v-model="batchFetchForm.symbols"
                rows="4"
                class="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-violet-500 focus:border-violet-500 bg-gray-50 focus:bg-white font-mono text-sm transition-all"
                placeholder="每行一个标的代码，或用逗号分隔&#10;例如：&#10;600000.SH&#10;600036.SH&#10;000001.SZ"
              ></textarea>
              <p class="text-xs text-gray-500 mt-1">支持每行一个或逗号分隔多个标的代码</p>
            </div>

            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">开始日期</label>
              <input
                v-model="batchFetchForm.startDate"
                type="date"
                class="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-violet-500 focus:border-violet-500 bg-gray-50 focus:bg-white transition-all"
              />
            </div>

            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">结束日期</label>
              <input
                v-model="batchFetchForm.endDate"
                type="date"
                class="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-violet-500 focus:border-violet-500 bg-gray-50 focus:bg-white transition-all"
              />
            </div>

            <div v-if="batchFetchResults.length > 0" class="bg-gray-50 rounded-lg p-4">
              <h3 class="text-sm font-medium text-gray-900 mb-2">获取结果</h3>
              <div class="max-h-32 overflow-y-auto text-sm">
                <div v-for="(result, index) in batchFetchResults" :key="index" class="flex justify-between items-center py-1">
                  <span class="text-gray-700">{{ result.symbol }}</span>
                  <span :class="result.count > 0 ? 'text-green-600' : 'text-yellow-600'">{{ result.count }} 条</span>
                </div>
              </div>
            </div>
          </div>

          <div class="px-6 py-4 bg-gray-50 flex justify-end space-x-3">
            <button
              @click="showBatchFetchDialog = false"
              :disabled="batchFetching"
              class="px-4 py-2 border rounded-lg hover:bg-gray-100 disabled:opacity-50 transition-colors"
            >
              关闭
            </button>
            <button
              @click="handleBatchFetchKline"
              :disabled="batchFetching"
              class="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:bg-gray-400 disabled:cursor-not-allowed flex items-center transition-colors"
            >
              <svg v-if="batchFetching" class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              {{ batchFetching ? '获取中...' : '批量获取' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div
        v-if="showDeleteDialog"
        class="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4"
        @click.self="showDeleteDialog = false"
      >
        <div class="bg-white rounded-xl shadow-xl w-full max-w-sm overflow-hidden" @click.stop>
          <div class="px-6 py-4 border-b">
            <h2 class="text-xl font-semibold">确认删除</h2>
          </div>

          <div class="p-6">
            <p class="text-gray-700">确定要删除标的 <span class="font-semibold text-gray-900">{{ deletingSymbol }}</span> 及其所有 K 线数据吗？</p>
            <p class="text-sm text-red-500 mt-2">此操作不可撤销。</p>
          </div>

          <div class="px-6 py-4 bg-gray-50 flex justify-end space-x-3">
            <button
              @click="showDeleteDialog = false"
              :disabled="deleting"
              class="px-4 py-2 border rounded-lg hover:bg-gray-100 disabled:opacity-50 transition-colors"
            >
              取消
            </button>
            <button
              @click="handleDeleteSymbol"
              :disabled="deleting"
              class="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:bg-gray-400 disabled:cursor-not-allowed flex items-center transition-colors"
            >
              <svg v-if="deleting" class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              {{ deleting ? '删除中...' : '确认删除' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div
        v-if="showSettingsPanel"
        class="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4"
        @click.self="closeSettings"
      >
        <div class="bg-white rounded-xl shadow-xl w-full max-w-md overflow-hidden">
          <div class="px-6 py-4 border-b flex justify-between items-center">
            <h2 class="text-xl font-semibold">图表设置</h2>
            <button
              @click="closeSettings"
              class="text-gray-400 hover:text-gray-600 transition-colors"
            >
              <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <div class="p-6 space-y-6">
            <!-- MA Periods -->
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2">MA 周期</label>
              <div class="flex flex-wrap gap-3">
                <div
                  v-for="p in maPeriodOptions"
                  :key="p"
                  class="flex items-center gap-1.5"
                >
                  <button
                    @click="toggleMaPeriod(p)"
                    class="px-3 py-1 text-xs rounded-full border transition-all font-medium"
                    :class="selectedMaPeriods.includes(p)
                      ? 'text-white border-transparent'
                      : 'bg-white text-gray-500 border-gray-300 hover:border-gray-400'"
                    :style="selectedMaPeriods.includes(p) ? { backgroundColor: maColors[p], borderColor: maColors[p] } : {}"
                  >
                    MA{{ p }}
                  </button>
                  <label class="relative inline-flex items-center cursor-pointer">
                    <input
                      type="color"
                      v-model="maColors[p]"
                      class="sr-only"
                    />
                    <span
                      class="w-4 h-4 rounded-full border border-gray-300 inline-block"
                      :style="{ backgroundColor: maColors[p] }"
                      title="自定义颜色"
                    />
                  </label>
                </div>
              </div>
            </div>

            <!-- Indicators -->
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2">技术指标</label>
              <div class="flex flex-wrap gap-2">
                <button
                  v-for="ind in indicatorOptions"
                  :key="ind.key"
                  @click="toggleIndicator(ind.key)"
                  class="px-3 py-1 text-xs rounded-full border transition-all font-medium"
                  :class="activeIndicators.has(ind.key)
                    ? 'bg-blue-600 text-white border-blue-600'
                    : 'bg-white text-gray-500 border-gray-300 hover:border-blue-400'"
                >
                  {{ ind.label }}
                </button>
              </div>
            </div>
          </div>

          <div class="px-6 py-4 bg-gray-50 flex justify-end space-x-3">
            <button
              @click="closeSettings"
              class="px-4 py-2 border rounded-lg hover:bg-gray-100 transition-colors"
            >
              取消
            </button>
            <button
              @click="confirmSettings"
              class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              确定
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

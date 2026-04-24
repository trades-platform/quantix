<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { dataApi, symbolPoolApi } from '../api'
import { useDataStore } from '../stores/data'
import { useNotificationStore } from '../stores/notification'
import { storeToRefs } from 'pinia'
import KlineChart from '../components/KlineChart.vue'

const dataStore = useDataStore()
const { symbols, klineData, loading, selectedSymbol, hasData } = storeToRefs(dataStore)
const notificationStore = useNotificationStore()

const klineLoading = ref(false)
const klineStats = ref(null)

const searchQuery = ref('')
const symbolPools = ref([])
const poolLoading = ref(false)
const poolSaving = ref(false)
const showPoolDialog = ref(false)
const editingPoolName = ref('')
const poolForm = ref({
  name: '',
  description: '',
  symbols: ''
})

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

const filteredSymbols = computed(() => {
  if (!searchQuery.value) return symbols.value
  const query = searchQuery.value.toLowerCase()
  return symbols.value.filter((s) => {
    const symbol = typeof s === 'string' ? s : s.symbol
    const name = typeof s === 'string' ? '' : (s.name || '')
    return symbol.toLowerCase().includes(query) || name.toLowerCase().includes(query)
  })
})

const parsedPoolSymbols = computed(() => {
  return Array.from(new Set(
    poolForm.value.symbols
      .split(/[\n,]+/)
      .map((item) => item.trim().toUpperCase())
      .filter((item) => item)
  ))
})

const fetchSymbols = async () => {
  try {
    await dataStore.fetchSymbols(dataApi)
  } catch (error) {
    notificationStore.error('获取标的列表失败')
  }
}

const fetchSymbolPools = async () => {
  poolLoading.value = true
  try {
    const response = await symbolPoolApi.list()
    symbolPools.value = response.data
  } catch (error) {
    notificationStore.error('获取标的池列表失败')
  } finally {
    poolLoading.value = false
  }
}

const fetchKline = async () => {
  if (!selectedSymbol.value) return

  klineLoading.value = true
  try {
    await dataStore.fetchKline(dataApi, {
      symbol: selectedSymbol.value,
      limit: 500,
    })
    calculateStats()
  } catch (error) {
    notificationStore.error('获取K线数据失败')
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
    high: Math.max(...data.map((d) => d.high)).toFixed(2),
    low: Math.min(...data.map((d) => d.low)).toFixed(2),
    avgVolume: Math.round(data.reduce((sum, d) => sum + d.volume, 0) / data.length).toLocaleString(),
  }
}

const formatDate = (dateStr) => {
  return new Date(dateStr).toLocaleString('zh-CN', { hour12: false })
}

const toLocalDateStr = (date) => {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

const openFetchDialog = () => {
  const today = new Date()
  const lastMonth = new Date(today)
  lastMonth.setMonth(lastMonth.getMonth() - 1)

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
  const lastMonth = new Date(today)
  lastMonth.setMonth(lastMonth.getMonth() - 1)

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

  const symbols = symbolsText.split(/[\n,]+/).map(s => s.trim()).filter(s => s)
  if (symbols.length === 0) {
    notificationStore.warning('请输入有效的标的代码')
    return
  }

  batchFetching.value = true
  try {
    const result = await dataStore.fetchBatchKline(dataApi, {
      symbols,
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

const resetPoolForm = () => {
  poolForm.value = {
    name: '',
    description: '',
    symbols: ''
  }
  editingPoolName.value = ''
}

const openPoolDialog = (pool = null) => {
  if (pool) {
    editingPoolName.value = pool.name
    poolForm.value = {
      name: pool.name,
      description: pool.description || '',
      symbols: pool.symbols.join(', ')
    }
  } else {
    resetPoolForm()
  }
  showPoolDialog.value = true
}

const closePoolDialog = () => {
  showPoolDialog.value = false
  resetPoolForm()
}

const handlePoolSubmit = async () => {
  const payload = {
    name: poolForm.value.name.trim(),
    description: poolForm.value.description.trim(),
    symbols: parsedPoolSymbols.value
  }

  if (!payload.name) {
    notificationStore.warning('请输入标的池名称')
    return
  }

  if (payload.symbols.length === 0) {
    notificationStore.warning('请至少填写一个标的代码')
    return
  }

  poolSaving.value = true
  try {
    if (editingPoolName.value) {
      await symbolPoolApi.update(editingPoolName.value, payload)
      notificationStore.success(`已更新标的池 @${payload.name}`)
    } else {
      await symbolPoolApi.create(payload)
      notificationStore.success(`已创建标的池 @${payload.name}`)
    }
    closePoolDialog()
    await fetchSymbolPools()
  } catch (error) {
    notificationStore.error('保存标的池失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    poolSaving.value = false
  }
}

const deletePool = async (pool) => {
  if (!window.confirm(`确认删除标的池 @${pool.name} 吗？`)) {
    return
  }

  try {
    await symbolPoolApi.delete(pool.name)
    notificationStore.success(`已删除标的池 @${pool.name}`)
    await fetchSymbolPools()
  } catch (error) {
    notificationStore.error('删除标的池失败: ' + (error.response?.data?.detail || error.message))
  }
}

const selectSymbol = (symbol) => {
  selectedSymbol.value = symbol
  fetchKline()
}

onMounted(() => {
  Promise.all([fetchSymbols(), fetchSymbolPools()])
})

watch(selectedSymbol, () => {
  if (selectedSymbol.value) {
    fetchKline()
  }
})
</script>

<template>
  <div class="p-4 sm:p-6 lg:p-8">
    <div class="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-4 mb-6">
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

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
      <div class="lg:col-span-1 space-y-6">
        <div class="bg-white rounded-xl shadow-sm border border-gray-100">
          <div class="p-4 border-b">
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

          <div class="max-h-96 overflow-y-auto">
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
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <div class="p-4 border-t bg-gray-50">
            <div class="flex justify-between text-sm">
              <span class="text-gray-600">总计:</span>
              <span class="font-medium">{{ symbols.length }} 个标的</span>
            </div>
          </div>
        </div>

        <div class="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
          <div class="px-4 py-4 border-b flex items-start justify-between gap-4">
            <div>
              <h3 class="font-semibold text-gray-900">标的池</h3>
              <p class="text-sm text-gray-500 mt-1">把一组代码保存成可复用目标，供回测和批量操作使用</p>
            </div>
            <button
              @click="openPoolDialog()"
              class="shrink-0 bg-blue-600 text-white px-3 py-2 rounded-lg hover:bg-blue-700 transition-colors"
            >
              新建
            </button>
          </div>

          <div v-if="poolLoading" class="p-6 text-center text-gray-500">
            <div class="inline-block animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
            <p class="mt-2 text-sm">加载标的池中...</p>
          </div>
          <div v-else-if="symbolPools.length === 0" class="p-6 text-center text-gray-500">
            <p class="text-sm">暂无标的池</p>
            <p class="text-xs mt-1">例如把 `588000.SH,159682.SZ` 保存为一个可复用组合</p>
          </div>
          <div v-else class="divide-y divide-gray-100">
            <div v-for="pool in symbolPools" :key="pool.name" class="p-4">
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                  <div class="font-medium text-gray-900 truncate">@{{ pool.name }}</div>
                  <p class="text-sm text-gray-500 mt-1">{{ pool.description || '无描述' }}</p>
                  <p class="text-xs text-gray-400 mt-1">{{ pool.symbols.length }} 个标的</p>
                </div>
                <div class="flex items-center gap-2 shrink-0">
                  <button
                    @click="openPoolDialog(pool)"
                    class="px-2.5 py-1.5 text-sm border rounded-lg hover:bg-gray-50 transition-colors"
                  >
                    编辑
                  </button>
                  <button
                    @click="deletePool(pool)"
                    class="px-2.5 py-1.5 text-sm border border-red-200 text-red-600 rounded-lg hover:bg-red-50 transition-colors"
                  >
                    删除
                  </button>
                </div>
              </div>

              <div class="flex flex-wrap gap-2 mt-3">
                <span
                  v-for="code in pool.symbols"
                  :key="code"
                  class="px-2.5 py-1 rounded-full bg-blue-50 text-blue-700 text-xs font-medium"
                >
                  {{ code }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="lg:col-span-2">
        <div v-if="!selectedSymbol" class="bg-white rounded-xl shadow-sm border border-gray-100 p-12 text-center">
          <svg class="mx-auto h-16 w-16 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
          <h3 class="mt-4 text-lg font-medium text-gray-900">请选择标的</h3>
          <p class="mt-2 text-gray-500">从左侧列表选择一个标的查看K线数据</p>
        </div>

        <div v-else>
          <div v-if="klineStats" class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
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

          <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
            <div class="flex justify-between items-center mb-4">
              <h3 class="text-lg font-semibold">K线图表 - {{ selectedSymbol }}</h3>
              <span v-if="klineStats" class="text-sm text-gray-600">{{ klineStats.dateRange }}</span>
            </div>
            <KlineChart v-if="hasData && !klineLoading" :data="klineData" height="400px" />
            <div v-else-if="klineLoading" class="h-64 flex items-center justify-center text-gray-500">
              <div class="inline-block animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
              <span class="ml-2">加载中...</span>
            </div>
            <div v-else class="h-64 flex items-center justify-center text-gray-500">
              暂无K线数据
            </div>
          </div>

          <div class="mt-6 bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
            <div class="px-6 py-4 border-b border-gray-100 flex justify-between items-center">
              <h3 class="text-lg font-semibold">数据明细</h3>
              <span class="text-sm text-gray-500">显示最近 20 条</span>
            </div>
            <div class="overflow-x-auto">
              <table class="min-w-full">
                <thead class="bg-gray-50">
                  <tr>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">日期</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">开盘</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">最高</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">最低</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">收盘</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">成交量</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">涨跌</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-gray-200 bg-white">
                  <tr v-if="klineData.length === 0 && !klineLoading">
                    <td colspan="7" class="px-6 py-8 text-center text-gray-500">暂无数据</td>
                  </tr>
                  <tr v-else v-for="(bar, index) in klineData.slice(0, 20)" :key="index" class="hover:bg-gray-50 transition-colors">
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {{ formatDate(bar.timestamp) }}
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{{ bar.open?.toFixed(2) }}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-red-600">{{ bar.high?.toFixed(2) }}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-green-600">{{ bar.low?.toFixed(2) }}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm font-medium" :class="bar.close >= bar.open ? 'text-red-600' : 'text-green-600'">
                      {{ bar.close?.toFixed(2) }}
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{{ bar.volume?.toLocaleString() }}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm">
                      <span
                        class="px-2 py-1 text-xs rounded"
                        :class="(bar.close - bar.open) / bar.open >= 0 ? 'bg-red-100 text-red-800' : 'bg-green-100 text-green-800'"
                      >
                        {{ ((bar.close - bar.open) / bar.open * 100).toFixed(2) }}%
                      </span>
                    </td>
                  </tr>
                </tbody>
              </table>
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
        v-if="showPoolDialog"
        class="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4"
        @click.self="closePoolDialog"
      >
        <div class="bg-white rounded-xl shadow-xl w-full max-w-lg overflow-hidden">
          <div class="px-6 py-4 border-b flex justify-between items-center">
            <h2 class="text-xl font-semibold">{{ editingPoolName ? '编辑标的池' : '新建标的池' }}</h2>
            <button
              @click="closePoolDialog"
              class="text-gray-400 hover:text-gray-600 transition-colors"
            >
              <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <div class="p-6 space-y-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">标的池名称 <span class="text-red-500">*</span></label>
              <input
                v-model="poolForm.name"
                type="text"
                class="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-gray-50 focus:bg-white transition-all"
                placeholder="例如: etf_core"
              />
              <p class="text-xs text-gray-500 mt-1">仅支持字母、数字、下划线和中划线</p>
            </div>

            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">描述</label>
              <input
                v-model="poolForm.description"
                type="text"
                class="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-gray-50 focus:bg-white transition-all"
                placeholder="例如: 核心 ETF 组合"
              />
            </div>

            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">标的代码 <span class="text-red-500">*</span></label>
              <textarea
                v-model="poolForm.symbols"
                rows="5"
                class="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-gray-50 focus:bg-white font-mono text-sm transition-all"
                placeholder="支持逗号或换行分隔&#10;例如：&#10;588000.SH,159682.SZ"
              ></textarea>
              <p class="text-xs text-gray-500 mt-1">提交时会自动去重并转成大写</p>
            </div>

            <div v-if="parsedPoolSymbols.length > 0" class="bg-gray-50 rounded-lg p-4">
              <h3 class="text-sm font-medium text-gray-900 mb-2">预览</h3>
              <div class="flex flex-wrap gap-2">
                <span
                  v-for="code in parsedPoolSymbols"
                  :key="code"
                  class="px-2.5 py-1 rounded-full bg-blue-50 text-blue-700 text-xs font-medium"
                >
                  {{ code }}
                </span>
              </div>
            </div>
          </div>

          <div class="px-6 py-4 bg-gray-50 flex justify-end space-x-3">
            <button
              @click="closePoolDialog"
              :disabled="poolSaving"
              class="px-4 py-2 border rounded-lg hover:bg-gray-100 disabled:opacity-50 transition-colors"
            >
              取消
            </button>
            <button
              @click="handlePoolSubmit"
              :disabled="poolSaving"
              class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed flex items-center transition-colors"
            >
              <svg v-if="poolSaving" class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              {{ poolSaving ? '保存中...' : '保存标的池' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

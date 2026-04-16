<script setup>
import { ref, computed, onMounted } from 'vue'
import { dataApi } from '../api'
import KlineChart from '../components/KlineChart.vue'

const symbols = ref([])
const loading = ref(false)
const selectedSymbol = ref('')
const klineData = ref([])
const klineLoading = ref(false)
const klineStats = ref(null)

const importForm = ref({
  symbol: '',
  file: null,
})

const showImportDialog = ref(false)
const importing = ref(false)

// 搜索关键词
const searchQuery = ref('')

const filteredSymbols = computed(() => {
  if (!searchQuery.value) return symbols.value
  return symbols.value.filter((s) =>
    s.toLowerCase().includes(searchQuery.value.toLowerCase())
  )
})

const fetchSymbols = async () => {
  loading.value = true
  try {
    const response = await dataApi.getSymbols()
    symbols.value = response.data
  } catch (error) {
    console.error('获取标的列表失败:', error)
  } finally {
    loading.value = false
  }
}

const fetchKline = async () => {
  if (!selectedSymbol.value) return

  klineLoading.value = true
  try {
    const response = await dataApi.getKline({
      symbol: selectedSymbol.value,
      limit: 500,
    })
    klineData.value = response.data
    calculateStats()
  } catch (error) {
    console.error('获取K线数据失败:', error)
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

const handleFileChange = (event) => {
  importForm.value.file = event.target.files[0]
}

const importKline = async () => {
  if (!importForm.value.symbol || !importForm.value.file) {
    alert('请填写完整信息')
    return
  }

  importing.value = true
  const formData = new FormData()
  formData.append('symbol', importForm.value.symbol)
  formData.append('file', importForm.value.file)

  try {
    const response = await dataApi.importKline(formData)
    const count = response.data.count || 0
    alert(`导入成功，共导入 ${count} 条数据`)
    showImportDialog.value = false
    importForm.value = { symbol: '', file: null }
    await fetchSymbols()
  } catch (error) {
    console.error('导入失败:', error)
    alert('导入失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    importing.value = false
  }
}

const formatDate = (dateStr) => {
  return new Date(dateStr).toLocaleDateString('zh-CN')
}

const downloadTemplate = () => {
  const csv = 'timestamp,open,high,low,close,volume\n2024-01-01,10.50,10.80,10.40,10.70,1000000\n2024-01-02,10.70,10.90,10.60,10.85,1200000'
  const blob = new Blob([csv], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'kline_template.csv'
  a.click()
  URL.revokeObjectURL(url)
}

onMounted(() => {
  fetchSymbols()
})
</script>

<template>
  <div class="p-8">
    <div class="flex justify-between items-center mb-6">
      <div>
        <h1 class="text-3xl font-bold text-gray-900">数据管理</h1>
        <p class="mt-1 text-gray-600">管理K线数据和查看行情信息</p>
      </div>
      <button
        @click="showImportDialog = true"
        class="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 flex items-center"
      >
        <svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
        </svg>
        导入数据
      </button>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
      <!-- 左侧：标的列表 -->
      <div class="lg:col-span-1">
        <div class="bg-white rounded-lg shadow">
          <!-- 搜索框 -->
          <div class="p-4 border-b">
            <input
              v-model="searchQuery"
              type="text"
              placeholder="搜索标的代码..."
              class="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>

          <!-- 标的列表 -->
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
              <div
                v-for="symbol in filteredSymbols"
                :key="symbol"
                @click="selectedSymbol = symbol; fetchKline()"
                class="px-4 py-3 hover:bg-gray-50 cursor-pointer border-b last:border-b-0"
                :class="{ 'bg-blue-50 border-l-4 border-l-blue-500': selectedSymbol === symbol }"
              >
                <div class="font-medium text-gray-900">{{ symbol }}</div>
                <div class="text-xs text-gray-500 mt-1">点击查看K线数据</div>
              </div>
            </div>
          </div>

          <!-- 统计信息 -->
          <div class="p-4 border-t bg-gray-50">
            <div class="flex justify-between text-sm">
              <span class="text-gray-600">总计:</span>
              <span class="font-medium">{{ symbols.length }} 个标的</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧：K线预览 -->
      <div class="lg:col-span-2">
        <div v-if="!selectedSymbol" class="bg-white rounded-lg shadow p-12 text-center">
          <svg class="mx-auto h-16 w-16 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
          <h3 class="mt-4 text-lg font-medium text-gray-900">请选择标的</h3>
          <p class="mt-2 text-gray-600">从左侧列表选择一个标的查看K线数据</p>
        </div>

        <div v-else>
          <!-- 统计信息 -->
          <div v-if="klineStats" class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div class="bg-white rounded-lg shadow p-4">
              <p class="text-xs text-gray-600">数据点数</p>
              <p class="text-lg font-bold mt-1">{{ klineStats.dataPoints }}</p>
            </div>
            <div class="bg-white rounded-lg shadow p-4">
              <p class="text-xs text-gray-600">区间收益</p>
              <p class="text-lg font-bold mt-1" :class="parseFloat(klineStats.totalReturn) >= 0 ? 'text-red-600' : 'text-green-600'">
                {{ klineStats.totalReturn }}%
              </p>
            </div>
            <div class="bg-white rounded-lg shadow p-4">
              <p class="text-xs text-gray-600">最高价</p>
              <p class="text-lg font-bold mt-1 text-red-600">{{ klineStats.high }}</p>
            </div>
            <div class="bg-white rounded-lg shadow p-4">
              <p class="text-xs text-gray-600">最低价</p>
              <p class="text-lg font-bold mt-1 text-green-600">{{ klineStats.low }}</p>
            </div>
          </div>

          <!-- K线图表 -->
          <div class="bg-white rounded-lg shadow p-6">
            <div class="flex justify-between items-center mb-4">
              <h3 class="text-lg font-semibold">K线图表 - {{ selectedSymbol }}</h3>
              <span v-if="klineStats" class="text-sm text-gray-600">{{ klineStats.dateRange }}</span>
            </div>
            <KlineChart v-if="klineData.length > 0" :data="klineData" height="400px" />
            <div v-else class="h-64 flex items-center justify-center text-gray-500">
              暂无K线数据
            </div>
          </div>

          <!-- 数据表格 -->
          <div class="mt-6 bg-white rounded-lg shadow overflow-hidden">
            <div class="px-6 py-4 border-b flex justify-between items-center">
              <h3 class="text-lg font-semibold">数据明细</h3>
              <span class="text-sm text-gray-500">显示最近 20 条</span>
            </div>
            <div class="overflow-x-auto">
              <table class="min-w-full">
                <thead class="bg-gray-50">
                  <tr>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">日期</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">开盘</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">最高</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">最低</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">收盘</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">成交量</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">涨跌</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-gray-200">
                  <tr v-if="klineData.length === 0 && !klineLoading">
                    <td colspan="7" class="px-6 py-8 text-center text-gray-500">暂无数据</td>
                  </tr>
                  <tr v-else v-for="(bar, index) in klineData.slice(0, 20)" :key="index" class="hover:bg-gray-50">
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

    <!-- 导入对话框 -->
    <div
      v-if="showImportDialog"
      class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
    >
      <div class="bg-white rounded-lg shadow-xl w-full max-w-md">
        <div class="px-6 py-4 border-b flex justify-between items-center">
          <h2 class="text-xl font-semibold">导入K线数据</h2>
          <button @click="showImportDialog = false" class="text-gray-400 hover:text-gray-600">
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div class="p-6 space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">标的代码 <span class="text-red-500">*</span></label>
            <input
              v-model="importForm.symbol"
              type="text"
              class="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder="例如: 600000.SH"
            />
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">数据文件 (CSV) <span class="text-red-500">*</span></label>
            <input
              type="file"
              accept=".csv"
              @change="handleFileChange"
              class="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
            <p class="text-xs text-gray-500 mt-1">
              需包含列: timestamp, open, high, low, close, volume
            </p>
          </div>

          <!-- 模板下载 -->
          <div class="bg-blue-50 rounded-lg p-3">
            <div class="flex items-center justify-between">
              <div>
                <p class="text-sm font-medium text-blue-900">需要CSV模板?</p>
                <p class="text-xs text-blue-700">下载示例文件了解格式要求</p>
              </div>
              <button
                @click="downloadTemplate"
                class="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700"
              >
                下载模板
              </button>
            </div>
          </div>
        </div>

        <div class="px-6 py-4 bg-gray-50 flex justify-end space-x-3">
          <button
            @click="showImportDialog = false"
            :disabled="importing"
            class="px-4 py-2 border rounded-lg hover:bg-gray-100 disabled:opacity-50"
          >
            取消
          </button>
          <button
            @click="importKline"
            :disabled="importing"
            class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed flex items-center"
          >
            <svg v-if="importing" class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            {{ importing ? '导入中...' : '导入' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

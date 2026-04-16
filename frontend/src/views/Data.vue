<script setup>
import { ref, onMounted } from 'vue'
import { dataApi } from '../api'

const symbols = ref([])
const loading = ref(false)
const selectedSymbol = ref('')
const klineData = ref([])
const klineLoading = ref(false)

const importForm = ref({
  symbol: '',
  file: null,
})

const showImportDialog = ref(false)

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
      limit: 100,
    })
    klineData.value = response.data
  } catch (error) {
    console.error('获取K线数据失败:', error)
  } finally {
    klineLoading.value = false
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

  const formData = new FormData()
  formData.append('symbol', importForm.value.symbol)
  formData.append('file', importForm.value.file)

  try {
    await dataApi.importKline(formData)
    alert('导入成功')
    showImportDialog.value = false
    importForm.value = { symbol: '', file: null }
    await fetchSymbols()
  } catch (error) {
    console.error('导入失败:', error)
    alert('导入失败: ' + (error.response?.data?.detail || error.message))
  }
}

const formatDate = (dateStr) => {
  return new Date(dateStr).toLocaleDateString()
}

onMounted(() => {
  fetchSymbols()
})
</script>

<template>
  <div class="p-8">
    <div class="flex justify-between items-center">
      <h1 class="text-3xl font-bold text-gray-900">数据管理</h1>
      <button
        @click="showImportDialog = true"
        class="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700"
      >
        导入数据
      </button>
    </div>

    <!-- 标的列表 -->
    <div class="mt-8 bg-white rounded-lg shadow overflow-hidden">
      <div class="px-6 py-4 border-b">
        <h2 class="text-lg font-semibold">可用标的</h2>
      </div>
      <table class="min-w-full">
        <thead class="bg-gray-50">
          <tr>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">代码</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">操作</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-200">
          <tr v-if="loading">
            <td colspan="2" class="px-6 py-4 text-center text-gray-500">加载中...</td>
          </tr>
          <tr v-else-if="symbols.length === 0">
            <td colspan="2" class="px-6 py-4 text-center text-gray-500">暂无数据</td>
          </tr>
          <tr v-else v-for="symbol in symbols" :key="symbol" class="hover:bg-gray-50">
            <td class="px-6 py-4 whitespace-nowrap font-medium text-gray-900">
              {{ symbol }}
            </td>
            <td class="px-6 py-4 whitespace-nowrap">
              <button
                @click="selectedSymbol = symbol; fetchKline()"
                class="text-blue-600 hover:text-blue-800"
              >
                查看K线
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- K线预览 -->
    <div v-if="selectedSymbol" class="mt-8 bg-white rounded-lg shadow overflow-hidden">
      <div class="px-6 py-4 border-b flex justify-between items-center">
        <h2 class="text-lg font-semibold">K线数据 - {{ selectedSymbol }}</h2>
        <span v-if="klineLoading" class="text-sm text-gray-500">加载中...</span>
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
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-200">
            <tr v-if="klineData.length === 0 && !klineLoading">
              <td colspan="6" class="px-6 py-4 text-center text-gray-500">暂无K线数据</td>
            </tr>
            <tr v-else v-for="bar in klineData.slice(0, 20)" :key="bar.timestamp" class="hover:bg-gray-50">
              <td class="px-6 py-4 whitespace-nowrap text-gray-900">
                {{ formatDate(bar.timestamp) }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-gray-900">{{ bar.open?.toFixed(2) }}</td>
              <td class="px-6 py-4 whitespace-nowrap text-gray-900">{{ bar.high?.toFixed(2) }}</td>
              <td class="px-6 py-4 whitespace-nowrap text-gray-900">{{ bar.low?.toFixed(2) }}</td>
              <td class="px-6 py-4 whitespace-nowrap text-gray-900">{{ bar.close?.toFixed(2) }}</td>
              <td class="px-6 py-4 whitespace-nowrap text-gray-900">{{ bar.volume?.toLocaleString() }}</td>
            </tr>
          </tbody>
        </table>
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
            <label class="block text-sm font-medium text-gray-700 mb-1">标的代码</label>
            <input
              v-model="importForm.symbol"
              type="text"
              class="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder="例如: 600000.SH"
            />
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">数据文件</label>
            <input
              type="file"
              accept=".csv"
              @change="handleFileChange"
              class="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
            <p class="text-xs text-gray-500 mt-1">支持 CSV 格式，需包含: timestamp, open, high, low, close, volume</p>
          </div>
        </div>

        <div class="px-6 py-4 bg-gray-50 flex justify-end space-x-3">
          <button
            @click="showImportDialog = false"
            class="px-4 py-2 border rounded-lg hover:bg-gray-100"
          >
            取消
          </button>
          <button
            @click="importKline"
            class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            导入
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

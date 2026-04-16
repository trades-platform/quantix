<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { strategyApi, dataApi, backtestApi } from '../api'

const router = useRouter()

const strategies = ref([])
const symbols = ref([])
const loading = ref(false)
const running = ref(false)

const form = ref({
  strategy_id: null,
  symbol: '',
  start_date: '',
  end_date: '',
  initial_capital: 1000000,
  commission: 0.0003,
})

const fetchStrategies = async () => {
  try {
    const response = await strategyApi.list()
    strategies.value = response.data
  } catch (error) {
    console.error('获取策略列表失败:', error)
  }
}

const fetchSymbols = async () => {
  try {
    const response = await dataApi.getSymbols()
    symbols.value = response.data
  } catch (error) {
    console.error('获取标的列表失败:', error)
  }
}

const runBacktest = async () => {
  if (!form.value.strategy_id) {
    alert('请选择策略')
    return
  }
  if (!form.value.symbol) {
    alert('请选择标的')
    return
  }
  if (!form.value.start_date || !form.value.end_date) {
    alert('请选择日期范围')
    return
  }

  running.value = true
  try {
    const response = await backtestApi.create(form.value)
    const backtestId = response.data.id
    router.push(`/results?id=${backtestId}`)
  } catch (error) {
    console.error('运行回测失败:', error)
    alert('运行回测失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    running.value = false
  }
}

// 设置默认日期范围
const setDefaultDates = () => {
  const end = new Date()
  const start = new Date()
  start.setFullYear(start.getFullYear() - 1)

  form.value.end_date = end.toISOString().split('T')[0]
  form.value.start_date = start.toISOString().split('T')[0]
}

onMounted(() => {
  fetchStrategies()
  fetchSymbols()
  setDefaultDates()
})
</script>

<template>
  <div class="p-8">
    <h1 class="text-3xl font-bold text-gray-900">回测配置</h1>
    <p class="mt-2 text-gray-600">配置参数并运行策略回测</p>

    <div class="mt-8 max-w-2xl">
      <div class="bg-white rounded-lg shadow p-6">
        <form @submit.prevent="runBacktest" class="space-y-6">
          <!-- 策略选择 -->
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">选择策略</label>
            <select
              v-model="form.strategy_id"
              class="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              :disabled="loading"
            >
              <option value="">请选择策略</option>
              <option v-for="strategy in strategies" :key="strategy.id" :value="strategy.id">
                {{ strategy.name }}
              </option>
            </select>
          </div>

          <!-- 标的选择 -->
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">选择标的</label>
            <select
              v-model="form.symbol"
              class="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              :disabled="loading"
            >
              <option value="">请选择标的</option>
              <option v-for="symbol in symbols" :key="symbol" :value="symbol">
                {{ symbol }}
              </option>
            </select>
          </div>

          <!-- 日期范围 -->
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2">开始日期</label>
              <input
                v-model="form.start_date"
                type="date"
                class="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2">结束日期</label>
              <input
                v-model="form.end_date"
                type="date"
                class="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
          </div>

          <!-- 初始资金 -->
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">初始资金</label>
            <div class="relative">
              <span class="absolute left-3 top-2 text-gray-500">¥</span>
              <input
                v-model.number="form.initial_capital"
                type="number"
                step="10000"
                min="10000"
                class="w-full pl-8 pr-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
          </div>

          <!-- 手续费率 -->
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">手续费率</label>
            <div class="relative">
              <input
                v-model.number="form.commission"
                type="number"
                step="0.0001"
                min="0"
                max="1"
                class="w-full px-3 py-2 pr-12 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
              <span class="absolute right-3 top-2 text-gray-500">比例</span>
            </div>
            <p class="text-xs text-gray-500 mt-1">默认 0.03%，即万分之三</p>
          </div>

          <!-- 提交按钮 -->
          <div class="flex justify-end">
            <button
              type="submit"
              :disabled="running"
              class="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
            >
              {{ running ? '运行中...' : '运行回测' }}
            </button>
          </div>
        </form>
      </div>

      <!-- 参数说明 -->
      <div class="mt-6 bg-blue-50 rounded-lg p-4">
        <h3 class="font-medium text-blue-900 mb-2">参数说明</h3>
        <ul class="text-sm text-blue-800 space-y-1">
          <li>• <strong>初始资金</strong>：回测账户的起始资金量</li>
          <li>• <strong>手续费率</strong>：每笔交易的手续费比例，0.0003 表示万分之三</li>
          <li>• <strong>日期范围</strong>：回测使用的历史数据时间段</li>
        </ul>
      </div>
    </div>
  </div>
</template>

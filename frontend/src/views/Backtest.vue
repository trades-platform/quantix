<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { strategyApi, dataApi, backtestApi, symbolPoolApi } from '../api'
import { useBacktestStore } from '../stores/backtest'
import { useNotificationStore } from '../stores/notification'
import { storeToRefs } from 'pinia'

const router = useRouter()
const backtestStore = useBacktestStore()
const { running } = storeToRefs(backtestStore)
const notificationStore = useNotificationStore()

const strategies = ref([])
const symbols = ref([])
const symbolPools = ref([])
const loading = ref(true)

const form = ref({
  strategy_id: null,
  target_type: 'symbol',
  symbol: '',
  pool_name: '',
  start_date: '',
  end_date: '',
  initial_capital: 1000000,
  commission: 0.0003,
  period: '1min',
  adjust: 'hfq',
})

const formErrors = ref({
  strategy_id: '',
  symbol: '',
  pool_name: '',
  start_date: '',
  end_date: '',
  initial_capital: '',
  commission: '',
})

const presets = [
  { name: '近一个月', days: 30 },
  { name: '近三个月', days: 90 },
  { name: '近半年', days: 180 },
  { name: '近一年', days: 365 },
]

const selectedStrategy = computed(() => {
  return strategies.value.find((s) => s.id === form.value.strategy_id)
})

const selectedPool = computed(() => {
  return symbolPools.value.find((pool) => pool.name === form.value.pool_name)
})

const selectedTargetLabel = computed(() => {
  if (form.value.target_type === 'pool') {
    return form.value.pool_name ? `@${form.value.pool_name}` : '-'
  }
  return form.value.symbol || '-'
})

const selectedTargetCount = computed(() => {
  if (form.value.target_type === 'pool') {
    return selectedPool.value?.symbols?.length || 0
  }
  return form.value.symbol ? 1 : 0
})

const dateRangeError = computed(() => {
  if (!form.value.start_date || !form.value.end_date) return ''
  const start = new Date(form.value.start_date)
  const end = new Date(form.value.end_date)
  const daysDiff = Math.ceil((end - start) / (1000 * 60 * 60 * 24))
  if (daysDiff < 7) {
    return '回测期间至少需要7天'
  }
  if (daysDiff > 365 * 5) {
    return '回测期间不能超过5年'
  }
  return ''
})

const validateForm = () => {
  let isValid = true
  formErrors.value = {
    strategy_id: '',
    symbol: '',
    pool_name: '',
    start_date: '',
    end_date: '',
    initial_capital: '',
    commission: '',
  }

  if (!form.value.strategy_id) {
    formErrors.value.strategy_id = '请选择策略'
    isValid = false
  }

  if (form.value.target_type === 'pool') {
    if (!form.value.pool_name) {
      formErrors.value.pool_name = '请选择标的池'
      isValid = false
    }
  } else if (!form.value.symbol) {
    formErrors.value.symbol = '请选择标的'
    isValid = false
  }

  if (!form.value.start_date) {
    formErrors.value.start_date = '请选择开始日期'
    isValid = false
  }

  if (!form.value.end_date) {
    formErrors.value.end_date = '请选择结束日期'
    isValid = false
  }

  if (form.value.start_date && form.value.end_date) {
    const start = new Date(form.value.start_date)
    const end = new Date(form.value.end_date)
    if (start >= end) {
      formErrors.value.end_date = '结束日期必须晚于开始日期'
      isValid = false
    } else if (dateRangeError.value) {
      formErrors.value.end_date = dateRangeError.value
      isValid = false
    }
  }

  if (!form.value.initial_capital || form.value.initial_capital < 10000) {
    formErrors.value.initial_capital = '初始资金不能少于 10,000 元'
    isValid = false
  } else if (form.value.initial_capital > 100000000) {
    formErrors.value.initial_capital = '初始资金不能超过 1 亿元'
    isValid = false
  }

  if (form.value.commission === null || form.value.commission === undefined || form.value.commission < 0) {
    formErrors.value.commission = '请输入手续费率'
    isValid = false
  } else if (form.value.commission > 0.1) {
    formErrors.value.commission = '手续费率不能超过 10%'
    isValid = false
  }

  return isValid
}

const runBacktest = async () => {
  if (!validateForm()) {
    notificationStore.warning('请检查表单填写是否正确')
    return
  }

  try {
    const payload = {
      strategy_id: form.value.strategy_id,
      start_date: form.value.start_date,
      end_date: form.value.end_date,
      initial_capital: form.value.initial_capital,
      commission: form.value.commission,
      period: form.value.period,
      adjust: form.value.adjust,
    }

    if (form.value.target_type === 'pool') {
      payload.pool_name = form.value.pool_name
    } else {
      payload.symbol = form.value.symbol
    }

    const result = await backtestStore.runBacktest(backtestApi, payload)
    notificationStore.success('回测任务已启动')
    router.push(`/results?id=${result.id}`)
  } catch (error) {
    notificationStore.error('运行回测失败: ' + (error.response?.data?.detail || error.message))
  }
}

const applyPreset = (days) => {
  const end = new Date()
  const start = new Date()
  start.setDate(start.getDate() - days)

  form.value.end_date = end.toISOString().split('T')[0]
  form.value.start_date = start.toISOString().split('T')[0]

  if (dateRangeError.value) {
    formErrors.value.end_date = dateRangeError.value
  }
}

const setDefaultDates = () => {
  applyPreset(365)
}

const formatCurrency = (value) => {
  return new Intl.NumberFormat('zh-CN', {
    style: 'currency',
    currency: 'CNY',
  }).format(value)
}

const formatPercent = (value) => {
  return (value * 100).toFixed(2) + '%'
}

onMounted(() => {
  Promise.all([
    strategyApi.list().then(r => strategies.value = r.data).catch(() => {
      notificationStore.error('获取策略列表失败')
    }),
    dataApi.getSymbols().then(r => symbols.value = r.data).catch(() => {
      notificationStore.error('获取标的列表失败')
    }),
    symbolPoolApi.list().then(r => symbolPools.value = r.data).catch(() => {
      notificationStore.error('获取标的池列表失败')
    }),
  ]).finally(() => {
    loading.value = false
    setDefaultDates()
  })
})
</script>

<template>
  <div class="p-4 sm:p-6 lg:p-8">
    <div class="mb-6">
      <h1 class="text-3xl font-bold text-gray-900">回测配置</h1>
      <div class="flex items-center mt-2">
        <div class="h-[3px] w-12 rounded-full bg-gradient-to-r from-blue-500 to-blue-600 mr-3"></div>
        <p class="text-gray-500">配置参数并运行策略回测</p>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
      <div class="lg:col-span-2">
        <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
          <form @submit.prevent="runBacktest" class="space-y-6">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2">
                选择策略 <span class="text-red-500">*</span>
              </label>
              <select
                v-model="form.strategy_id"
                class="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-gray-50 focus:bg-white transition-all"
                :class="{ 'border-red-500 focus:border-red-500 focus:ring-red-500/20': formErrors.strategy_id }"
                :disabled="loading"
              >
                <option value="">请选择策略</option>
                <option v-for="strategy in strategies" :key="strategy.id" :value="strategy.id">
                  {{ strategy.name }} - {{ strategy.description || '无描述' }}
                </option>
              </select>
              <p v-if="formErrors.strategy_id" class="text-sm text-red-600 mt-1">
                {{ formErrors.strategy_id }}
              </p>
            </div>

            <div class="space-y-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">
                  回测目标 <span class="text-red-500">*</span>
                </label>
                <div class="grid grid-cols-2 gap-3">
                  <button
                    type="button"
                    @click="form.target_type = 'symbol'"
                    class="px-4 py-3 border rounded-lg text-left transition-all"
                    :class="form.target_type === 'symbol' ? 'border-blue-500 bg-blue-50 text-blue-700 shadow-sm' : 'border-gray-200 bg-white text-gray-700 hover:bg-gray-50'"
                  >
                    <div class="font-medium">单标的</div>
                    <div class="text-xs mt-1 text-gray-500">选择一个具体代码运行回测</div>
                  </button>
                  <button
                    type="button"
                    @click="form.target_type = 'pool'"
                    class="px-4 py-3 border rounded-lg text-left transition-all"
                    :class="form.target_type === 'pool' ? 'border-blue-500 bg-blue-50 text-blue-700 shadow-sm' : 'border-gray-200 bg-white text-gray-700 hover:bg-gray-50'"
                  >
                    <div class="font-medium">标的池</div>
                    <div class="text-xs mt-1 text-gray-500">复用一组已保存的代码集合</div>
                  </button>
                </div>
              </div>

              <div v-if="form.target_type === 'symbol'">
                <label class="block text-sm font-medium text-gray-700 mb-2">
                  选择标的 <span class="text-red-500">*</span>
                </label>
                <select
                  v-model="form.symbol"
                  class="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-gray-50 focus:bg-white transition-all"
                  :class="{ 'border-red-500 focus:border-red-500 focus:ring-red-500/20': formErrors.symbol }"
                  :disabled="loading"
                >
                  <option value="">请选择标的</option>
                  <option v-for="item in symbols" :key="item.symbol" :value="item.symbol">
                    {{ item.symbol }}{{ item.name ? ` · ${item.name}` : '' }}
                  </option>
                </select>
                <p v-if="formErrors.symbol" class="text-sm text-red-600 mt-1">
                  {{ formErrors.symbol }}
                </p>
              </div>

              <div v-else>
                <label class="block text-sm font-medium text-gray-700 mb-2">
                  选择标的池 <span class="text-red-500">*</span>
                </label>
                <select
                  v-model="form.pool_name"
                  class="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-gray-50 focus:bg-white transition-all"
                  :class="{ 'border-red-500 focus:border-red-500 focus:ring-red-500/20': formErrors.pool_name }"
                  :disabled="loading"
                >
                  <option value="">请选择标的池</option>
                  <option v-for="pool in symbolPools" :key="pool.name" :value="pool.name">
                    @{{ pool.name }} · {{ pool.symbols.length }} 个标的
                  </option>
                </select>
                <p v-if="formErrors.pool_name" class="text-sm text-red-600 mt-1">
                  {{ formErrors.pool_name }}
                </p>
                <p v-else-if="selectedPool" class="text-xs text-gray-500 mt-1">
                  {{ selectedPool.description || '无描述' }} · {{ selectedPool.symbols.join(', ') }}
                </p>
              </div>
            </div>

            <div>
              <div class="flex justify-between items-center mb-2">
                <label class="block text-sm font-medium text-gray-700">
                  日期范围 <span class="text-red-500">*</span>
                </label>
                <div class="flex space-x-2">
                  <button
                    v-for="preset in presets"
                    :key="preset.name"
                    type="button"
                    @click="applyPreset(preset.days)"
                    class="text-xs px-2 py-1 border border-gray-200 rounded-lg bg-white hover:bg-gray-50 hover:border-gray-300 transition-all"
                  >
                    {{ preset.name }}
                  </button>
                </div>
              </div>
              <div class="grid grid-cols-2 gap-4">
                <div>
                  <input
                    v-model="form.start_date"
                    type="date"
                    class="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-gray-50 focus:bg-white transition-all"
                    :class="{ 'border-red-500 focus:border-red-500 focus:ring-red-500/20': formErrors.start_date }"
                  />
                  <p v-if="formErrors.start_date" class="text-sm text-red-600 mt-1">
                    {{ formErrors.start_date }}
                  </p>
                </div>
                <div>
                  <input
                    v-model="form.end_date"
                    type="date"
                    class="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-gray-50 focus:bg-white transition-all"
                    :class="{ 'border-red-500 focus:border-red-500 focus:ring-red-500/20': formErrors.end_date }"
                  />
                  <p v-if="formErrors.end_date" class="text-sm text-red-600 mt-1">
                    {{ formErrors.end_date }}
                  </p>
                </div>
              </div>
            </div>

            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2">
                初始资金 <span class="text-red-500">*</span>
              </label>
              <div class="relative">
                <span class="absolute left-3 top-2 text-gray-500">¥</span>
                <input
                  v-model.number="form.initial_capital"
                  type="number"
                  step="10000"
                  min="10000"
                  max="100000000"
                  class="w-full pl-8 pr-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-gray-50 focus:bg-white transition-all"
                  :class="{ 'border-red-500 focus:border-red-500 focus:ring-red-500/20': formErrors.initial_capital }"
                />
              </div>
              <p v-if="formErrors.initial_capital" class="text-sm text-red-600 mt-1">
                {{ formErrors.initial_capital }}
              </p>
              <p v-else class="text-xs text-gray-500 mt-1">
                建议初始资金不少于 10 万元
              </p>
            </div>

            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2">
                手续费率 <span class="text-red-500">*</span>
              </label>
              <div class="relative">
                <input
                  v-model.number="form.commission"
                  type="number"
                  step="0.0001"
                  min="0"
                  max="0.1"
                  class="w-full px-3 py-2 pr-16 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-gray-50 focus:bg-white transition-all"
                  :class="{ 'border-red-500 focus:border-red-500 focus:ring-red-500/20': formErrors.commission }"
                />
                <span class="absolute right-3 top-2 text-gray-500 text-sm">比例</span>
              </div>
              <p v-if="formErrors.commission" class="text-sm text-red-600 mt-1">
                {{ formErrors.commission }}
              </p>
              <div class="flex space-x-2 mt-2">
                <button
                  type="button"
                  @click="form.commission = 0.0003"
                  class="text-xs px-2 py-1 border border-gray-200 rounded-lg bg-white hover:bg-gray-50 hover:border-gray-300 transition-all"
                  :class="{ 'bg-blue-50 border-blue-500 text-blue-700 shadow-sm': form.commission === 0.0003 }"
                >
                  万分之三
                </button>
                <button
                  type="button"
                  @click="form.commission = 0.0001"
                  class="text-xs px-2 py-1 border border-gray-200 rounded-lg bg-white hover:bg-gray-50 hover:border-gray-300 transition-all"
                  :class="{ 'bg-blue-50 border-blue-500 text-blue-700 shadow-sm': form.commission === 0.0001 }"
                >
                  万分之一
                </button>
                <button
                  type="button"
                  @click="form.commission = 0.001"
                  class="text-xs px-2 py-1 border border-gray-200 rounded-lg bg-white hover:bg-gray-50 hover:border-gray-300 transition-all"
                  :class="{ 'bg-blue-50 border-blue-500 text-blue-700 shadow-sm': form.commission === 0.001 }"
                >
                  千分之一
                </button>
              </div>
            </div>

            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2">
                K线周期
              </label>
              <div class="flex space-x-2">
                <button
                  v-for="p in ['1min', '5min', '15min', '30min', '60min', '120min', '1D', '1W', '1M', '1Q']"
                  :key="p"
                  type="button"
                  @click="form.period = p"
                  class="text-sm px-3 py-1.5 border border-gray-200 rounded-lg bg-white hover:bg-gray-50 hover:border-gray-300 transition-all"
                  :class="{ 'bg-blue-50 border-blue-500 text-blue-700 shadow-sm': form.period === p }"
                >
                  {{ { '1D': '日线', '1W': '周线', '1M': '月线', '1Q': '季线', '120min': '2h' }[p] || p }}
                </button>
              </div>
              <p class="text-xs text-gray-500 mt-1">
                从1分钟数据合成，日线适合中长期策略
              </p>
            </div>

            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2">
                复权方式
              </label>
              <div class="flex space-x-2">
                <button
                  v-for="opt in [{value:'none',label:'不复权'}, {value:'qfq',label:'前复权'}, {value:'hfq',label:'后复权'}]"
                  :key="opt.value"
                  type="button"
                  @click="form.adjust = opt.value"
                  class="text-sm px-3 py-1.5 border border-gray-200 rounded-lg bg-white hover:bg-gray-50 hover:border-gray-300 transition-all"
                  :class="{ 'bg-blue-50 border-blue-500 text-blue-700 shadow-sm': form.adjust === opt.value }"
                >
                  {{ opt.label }}
                </button>
              </div>
              <p class="text-xs text-gray-500 mt-1">
                后复权保持历史价格连续，前复权保持最新价不变
              </p>
            </div>

            <div class="flex justify-end pt-4 border-t">
              <button
                type="submit"
                :disabled="running"
                class="bg-gradient-to-r from-blue-600 to-blue-700 text-white px-8 py-2.5 rounded-lg hover:from-blue-700 hover:to-blue-800 disabled:opacity-50 disabled:cursor-not-allowed flex items-center shadow-sm transition-all"
              >
                <svg v-if="running" class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                {{ running ? '运行中...' : '运行回测' }}
              </button>
            </div>
          </form>
        </div>
      </div>

      <div class="space-y-6 lg:sticky lg:top-6 lg:self-start">
        <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
          <h3 class="font-semibold text-gray-900 mb-4">配置摘要</h3>
          <div class="space-y-3 text-sm">
            <div class="flex justify-between">
              <span class="text-gray-600">策略:</span>
              <span class="font-medium">{{ selectedStrategy?.name || '-' }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-gray-600">标的:</span>
              <span class="font-medium">{{ selectedTargetLabel }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-gray-600">标的数量:</span>
              <span class="font-medium">{{ selectedTargetCount || '-' }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-gray-600">回测期间:</span>
              <span class="font-medium">
                {{ form.start_date }} 至 {{ form.end_date }}
              </span>
            </div>
            <div class="flex justify-between">
              <span class="text-gray-600">初始资金:</span>
              <span class="font-medium">{{ formatCurrency(form.initial_capital) }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-gray-600">手续费率:</span>
              <span class="font-medium">{{ formatPercent(form.commission) }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-gray-600">K线周期:</span>
              <span class="font-medium">{{ { '1D': '日线', '1W': '周线', '1M': '月线', '1Q': '季线', '120min': '2h' }[form.period] || form.period }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-gray-600">复权:</span>
              <span class="font-medium">{{ {none: '不复权', qfq: '前复权', hfq: '后复权'}[form.adjust] }}</span>
            </div>
          </div>
        </div>

        <div class="bg-blue-50 rounded-lg p-6">
          <h3 class="font-medium text-blue-900 mb-3">参数说明</h3>
          <ul class="text-sm text-blue-800 space-y-2">
            <li class="flex">
              <span class="mr-2 flex-shrink-0">•</span>
              <span><strong>初始资金</strong>：回测账户的起始资金，建议不少于 10 万元</span>
            </li>
            <li class="flex">
              <span class="mr-2 flex-shrink-0">•</span>
              <span><strong>手续费率</strong>：每笔交易的手续费比例，A股默认万分之三</span>
            </li>
            <li class="flex">
              <span class="mr-2 flex-shrink-0">•</span>
              <span><strong>日期范围</strong>：回测使用的历史数据时间段，需至少7天</span>
            </li>
          </ul>
        </div>

        <div v-if="selectedStrategy" class="bg-gray-50 rounded-lg p-6">
          <h3 class="font-medium text-gray-900 mb-2">策略说明</h3>
          <p class="text-sm text-gray-600">{{ selectedStrategy.description || '暂无描述' }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { strategyApi } from '../api'
import { useStrategiesStore } from '../stores/strategies'
import { useNotificationStore } from '../stores/notification'
import { storeToRefs } from 'pinia'
import CodeEditor from '../components/CodeEditor.vue'

const strategiesStore = useStrategiesStore()
const { strategies, loading, saving } = storeToRefs(strategiesStore)
const notificationStore = useNotificationStore()

const showEditor = ref(false)
const editingId = ref(null)
const deletingId = ref(null)

const form = ref({
  name: '',
  description: '',
  code: `# 双均线策略示例

def initialize(context):
    """策略初始化，设置参数"""
    context.short_period = 5   # 短期均线周期
    context.long_period = 20    # 长期均线周期

def handle_bar(context, bar):
    """处理单根K线，返回订单列表"""
    # 获取历史数据
    data = context.history(length=context.long_period)

    if len(data) < context.long_period:
        return []

    # 计算均线
    short_ma = data['close'].tail(context.short_period).mean()
    long_ma = data['close'].tail(context.long_period).mean()

    # 获取当前持仓
    position = context.position

    orders = []

    # 金叉买入
    if short_ma > long_ma and position == 0:
        orders.append({
            'symbol': context.symbol,
            'side': 'buy',
            'quantity': 100,  # 固定手数
        })
    # 死叉卖出
    elif short_ma < long_ma and position > 0:
        orders.append({
            'symbol': context.symbol,
            'side': 'sell',
            'quantity': position,
        })

    return orders
`,
})

const templates = {
  dual_ma: {
    name: '双均线策略',
    description: '基于5日和20日均线的交叉信号',
    code: `# 双均线策略

def initialize(context):
    context.short_period = 5
    context.long_period = 20

def handle_bar(context, bar):
    data = context.history(length=context.long_period)
    if len(data) < context.long_period:
        return []

    short_ma = data['close'].tail(context.short_period).mean()
    long_ma = data['close'].tail(context.long_period).mean()
    position = context.position

    orders = []
    if short_ma > long_ma and position == 0:
        orders.append({'symbol': context.symbol, 'side': 'buy', 'quantity': 100})
    elif short_ma < long_ma and position > 0:
        orders.append({'symbol': context.symbol, 'side': 'sell', 'quantity': position})

    return orders
`,
  },
  macd: {
    name: 'MACD策略',
    description: '基于MACD指标的买卖信号',
    code: `# MACD策略

def initialize(context):
    context.fast_period = 12
    context.slow_period = 26
    context.signal_period = 9

def handle_bar(context, bar):
    data = context.history(length=context.slow_period + context.signal_period)
    if len(data) < context.slow_period + context.signal_period:
        return []

    # 计算MACD（简化版）
    close = data['close']
    ema_fast = close.ewm(span=context.fast_period).mean()
    ema_slow = close.ewm(span=context.slow_period).mean()
    macd = ema_fast - ema_slow
    signal = macd.ewm(span=context.signal_period).mean()

    position = context.position
    orders = []

    # MACD上穿信号线买入
    if macd.iloc[-1] > signal.iloc[-1] and macd.iloc[-2] <= signal.iloc[-2]:
        if position == 0:
            orders.append({'symbol': context.symbol, 'side': 'buy', 'quantity': 100})
    # MACD下穿信号线卖出
    elif macd.iloc[-1] < signal.iloc[-1] and macd.iloc[-2] >= signal.iloc[-2]:
        if position > 0:
            orders.append({'symbol': context.symbol, 'side': 'sell', 'quantity': position})

    return orders
`,
  },
  rsi: {
    name: 'RSI策略',
    description: '基于RSI指标的超买超卖策略',
    code: `# RSI策略

def initialize(context):
    context.rsi_period = 14
    context.overbought = 70
    context.oversold = 30

def handle_bar(context, bar):
    data = context.history(length=context.rsi_period + 1)
    if len(data) < context.rsi_period + 1:
        return []

    # 计算RSI（简化版）
    close = data['close']
    delta = close.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.rolling(window=context.rsi_period).mean()
    avg_loss = loss.rolling(window=context.rsi_period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    current_rsi = rsi.iloc[-1]

    position = context.position
    orders = []

    # RSI超卖买入
    if current_rsi < context.oversold and position == 0:
        orders.append({'symbol': context.symbol, 'side': 'buy', 'quantity': 100})
    # RSI超买卖出
    elif current_rsi > context.overbought and position > 0:
        orders.append({'symbol': context.symbol, 'side': 'sell', 'quantity': position})

    return orders
`,
  },
}

const formErrors = ref({
  name: '',
  code: '',
})

const validateForm = () => {
  let isValid = true
  formErrors.value = { name: '', code: '' }

  if (!form.value.name.trim()) {
    formErrors.value.name = '请输入策略名称'
    isValid = false
  }

  if (!form.value.code.trim()) {
    formErrors.value.code = '请输入策略代码'
    isValid = false
  }

  return isValid
}

const createStrategy = async () => {
  if (!validateForm()) {
    return
  }

  try {
    await strategiesStore.createStrategy(strategyApi, form.value)
    notificationStore.success('策略创建成功')
    showEditor.value = false
    resetForm()
  } catch (error) {
    notificationStore.error('创建策略失败: ' + (error.response?.data?.detail || error.message))
  }
}

const editStrategy = async (id) => {
  try {
    const response = await strategyApi.get(id)
    const strategy = response.data
    editingId.value = id
    form.value = {
      name: strategy.name,
      description: strategy.description || '',
      code: strategy.code,
    }
    showEditor.value = true
  } catch (error) {
    notificationStore.error('获取策略详情失败')
  }
}

const updateStrategy = async () => {
  if (!validateForm()) {
    return
  }

  try {
    await strategiesStore.updateStrategy(strategyApi, editingId.value, form.value)
    notificationStore.success('策略更新成功')
    showEditor.value = false
    resetForm()
  } catch (error) {
    notificationStore.error('更新策略失败: ' + (error.response?.data?.detail || error.message))
  }
}

const confirmDelete = (id) => {
  deletingId.value = id
}

const deleteStrategy = async () => {
  try {
    await strategiesStore.deleteStrategy(strategyApi, deletingId.value)
    notificationStore.success('策略删除成功')
    deletingId.value = null
  } catch (error) {
    notificationStore.error('删除策略失败')
  }
}

const resetForm = () => {
  form.value = {
    name: '',
    description: '',
    code: templates.dual_ma.code,
  }
  editingId.value = null
  formErrors.value = { name: '', code: '' }
}

const openCreate = () => {
  resetForm()
  showEditor.value = true
}

const useTemplate = (templateKey) => {
  const template = templates[templateKey]
  form.value.name = template.name
  form.value.description = template.description
  form.value.code = template.code
  formErrors.value = { name: '', code: '' }
}

const formatDate = (dateStr) => {
  return new Date(dateStr).toLocaleString('zh-CN')
}

onMounted(() => {
  strategiesStore.fetchStrategies(strategyApi).catch(() => {
    notificationStore.error('获取策略列表失败')
  })
})
</script>

<template>
  <div class="p-4 sm:p-6 lg:p-8">
    <div class="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-4">
      <div>
        <h1 class="text-3xl font-bold text-gray-900">策略管理</h1>
        <div class="flex items-center mt-2">
          <div class="h-[3px] w-12 rounded-full bg-gradient-to-r from-blue-500 to-blue-600 mr-3"></div>
          <p class="text-gray-500">创建和管理您的量化交易策略</p>
        </div>
      </div>
      <button
        @click="openCreate"
        class="bg-gradient-to-r from-blue-600 to-blue-700 text-white px-5 py-2.5 rounded-lg hover:from-blue-700 hover:to-blue-800 flex items-center shadow-sm transition-all disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
        </svg>
        创建策略
      </button>
    </div>

    <div class="mt-8 bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
      <div class="px-6 py-4 border-b border-gray-100 flex justify-between items-center">
        <h2 class="text-lg font-semibold">策略列表</h2>
        <span class="text-sm text-gray-500 bg-gray-50 px-2.5 py-1 rounded-full">{{ strategies.length }} 个策略</span>
      </div>
      <table class="min-w-full">
        <thead class="bg-gray-50">
          <tr>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">名称</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">描述</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">创建时间</th>
            <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">操作</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-200 bg-white">
          <tr v-if="loading">
            <td colspan="4" class="px-6 py-12 text-center text-gray-500">
              <div class="flex flex-col items-center">
                <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                <p class="mt-2">加载中...</p>
              </div>
            </td>
          </tr>
          <tr v-else-if="strategies.length === 0">
            <td colspan="4" class="px-6 py-12 text-center">
              <div class="bg-gray-50/50 rounded-xl p-8 mx-4">
                <svg class="mx-auto h-12 w-12 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                <p class="mt-3 text-gray-600 font-medium">暂无策略</p>
                <p class="text-sm text-gray-400 mt-1">点击上方按钮创建第一个策略</p>
              </div>
            </td>
          </tr>
          <tr v-else v-for="strategy in strategies" :key="strategy.id" class="hover:bg-gray-50 transition-colors">
            <td class="px-6 py-4 whitespace-nowrap">
              <button type="button" @click="editStrategy(strategy.id)" class="font-medium text-gray-900 hover:text-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:rounded transition-colors">{{ strategy.name }}</button>
            </td>
            <td class="px-6 py-4">
              <div class="text-sm text-gray-600 max-w-xs truncate" :title="strategy.description">
                {{ strategy.description || '-' }}
              </div>
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
              {{ formatDate(strategy.created_at) }}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-right text-sm">
              <button
                @click="editStrategy(strategy.id)"
                class="text-blue-600 hover:text-blue-800 mr-4 transition-colors"
              >
                编辑
              </button>
              <button
                @click="confirmDelete(strategy.id)"
                class="text-red-600 hover:text-red-800 transition-colors"
              >
                删除
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <Teleport to="body">
      <div
        v-if="showEditor"
        class="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4"
        @click.self="showEditor = false"
      >
        <div class="bg-white rounded-xl shadow-xl w-full max-w-5xl max-h-[90vh] overflow-hidden flex flex-col">
          <div class="px-6 py-4 border-b flex justify-between items-center">
            <h2 class="text-xl font-semibold">
              {{ editingId ? '编辑策略' : '创建策略' }}
            </h2>
            <button
              @click="showEditor = false"
              class="text-gray-400 hover:text-gray-600 transition-colors"
            >
              <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <div class="flex-1 overflow-auto p-6">
            <div v-if="!editingId" class="mb-4">
              <label class="block text-sm font-medium text-gray-700 mb-2">使用模板</label>
              <div class="flex flex-wrap gap-2">
                <button
                  v-for="(template, key) in templates"
                  :key="key"
                  @click="useTemplate(key)"
                  class="px-3 py-2 text-sm border rounded-lg hover:bg-gray-50 transition-colors"
                >
                  {{ template.name }}
                </button>
              </div>
            </div>

            <div class="space-y-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">
                  策略名称 <span class="text-red-500">*</span>
                </label>
                <input
                  v-model="form.name"
                  type="text"
                  class="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-gray-50 focus:bg-white transition-all"
                  :class="{ 'border-red-500 focus:border-red-500 focus:ring-red-500/20': formErrors.name }"
                  placeholder="例如：双均线策略"
                />
                <p v-if="formErrors.name" class="text-sm text-red-600 mt-1">
                  {{ formErrors.name }}
                </p>
              </div>

              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">描述</label>
                <textarea
                  v-model="form.description"
                  rows="2"
                  class="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-gray-50 focus:bg-white transition-all resize-none"
                  placeholder="简要描述策略逻辑和特点"
                ></textarea>
              </div>

              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">
                  策略代码 <span class="text-red-500">*</span>
                </label>
                <div class="border rounded-lg overflow-hidden transition-all" :class="{ 'border-red-500 ring-2 ring-red-500/20': formErrors.code, 'border-gray-200 focus-within:border-blue-500 focus-within:ring-2 focus-within:ring-blue-500/20': !formErrors.code }" style="height: 400px">
                  <CodeEditor v-model="form.code" language="python" />
                </div>
                <p v-if="formErrors.code" class="text-sm text-red-600 mt-1">
                  {{ formErrors.code }}
                </p>
              </div>

              <div class="bg-blue-50 rounded-lg p-4">
                <h3 class="font-medium text-blue-900 mb-2">策略 API 说明</h3>
                <div class="text-sm text-blue-800 space-y-1">
                  <p><code class="bg-blue-100 px-1 rounded">initialize(context)</code> - 策略初始化，设置参数</p>
                  <p><code class="bg-blue-100 px-1 rounded">handle_bar(context, bar)</code> - 处理单根K线，返回订单列表</p>
                  <p class="mt-2"><strong>context 对象属性：</strong></p>
                  <ul class="list-disc list-inside ml-2 space-y-1">
                    <li><code>context.history(length)</code> - 获取历史数据</li>
                    <li><code>context.position</code> - 当前持仓</li>
                    <li><code>context.symbol</code> - 当前标的</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>

          <div class="px-6 py-4 bg-gray-50 flex justify-end space-x-3">
            <button
              @click="showEditor = false"
              class="px-4 py-2 border rounded-lg hover:bg-gray-100 transition-colors"
            >
              取消
            </button>
            <button
              @click="editingId ? updateStrategy() : createStrategy()"
              :disabled="saving"
              class="px-4 py-2 bg-gradient-to-r from-blue-600 to-blue-700 text-white rounded-lg hover:from-blue-700 hover:to-blue-800 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-sm"
            >
              {{ saving ? '保存中...' : (editingId ? '更新' : '创建') }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div
        v-if="deletingId"
        class="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4"
        @click.self="deletingId = null"
      >
        <div class="bg-white rounded-xl shadow-xl w-full max-w-md overflow-hidden">
          <div class="p-6">
            <div class="flex items-center gap-3 mb-3">
              <div class="w-10 h-10 rounded-full bg-red-100 flex items-center justify-center flex-shrink-0">
                <svg class="w-5 h-5 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </div>
              <h3 class="text-lg font-semibold text-gray-900">确认删除</h3>
            </div>
            <p class="text-gray-600 ml-13 pl-1">确定要删除这个策略吗？此操作无法撤销。</p>
          </div>
          <div class="px-6 py-4 bg-gray-50 flex justify-end space-x-3">
            <button
              @click="deletingId = null"
              class="px-4 py-2 border border-gray-300 rounded-lg hover:bg-white hover:border-gray-400 transition-all"
            >
              取消
            </button>
            <button
              @click="deleteStrategy"
              class="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors shadow-sm"
            >
              删除
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

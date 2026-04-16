<script setup>
import { ref, onMounted } from 'vue'
import { strategyApi } from '../api'

const strategies = ref([])
const loading = ref(false)
const showEditor = ref(false)
const editingId = ref(null)

const form = ref({
  name: '',
  description: '',
  code: '# 在此编写策略代码\n\ndef initialize(context):\n    """策略初始化"""\n    pass\n\ndef handle_bar(context, bar):\n    """处理单根K线，返回订单列表"""\n    return []',
})

const fetchStrategies = async () => {
  loading.value = true
  try {
    const response = await strategyApi.list()
    strategies.value = response.data
  } catch (error) {
    console.error('获取策略列表失败:', error)
  } finally {
    loading.value = false
  }
}

const createStrategy = async () => {
  try {
    await strategyApi.create(form.value)
    showEditor.value = false
    resetForm()
    await fetchStrategies()
  } catch (error) {
    console.error('创建策略失败:', error)
  }
}

const editStrategy = async (id) => {
  try {
    const response = await strategyApi.get(id)
    const strategy = response.data
    editingId.value = id
    form.value = {
      name: strategy.name,
      description: strategy.description,
      code: strategy.code,
    }
    showEditor.value = true
  } catch (error) {
    console.error('获取策略详情失败:', error)
  }
}

const updateStrategy = async () => {
  try {
    await strategyApi.update(editingId.value, form.value)
    showEditor.value = false
    resetForm()
    await fetchStrategies()
  } catch (error) {
    console.error('更新策略失败:', error)
  }
}

const deleteStrategy = async (id) => {
  if (!confirm('确定要删除这个策略吗？')) return
  try {
    await strategyApi.delete(id)
    await fetchStrategies()
  } catch (error) {
    console.error('删除策略失败:', error)
  }
}

const resetForm = () => {
  form.value = {
    name: '',
    description: '',
    code: '# 在此编写策略代码\n\ndef initialize(context):\n    """策略初始化"""\n    pass\n\ndef handle_bar(context, bar):\n    """处理单根K线，返回订单列表"""\n    return []',
  }
  editingId.value = null
}

const openCreate = () => {
  resetForm()
  showEditor.value = true
}

onMounted(() => {
  fetchStrategies()
})
</script>

<template>
  <div class="p-8">
    <div class="flex justify-between items-center">
      <h1 class="text-3xl font-bold text-gray-900">策略管理</h1>
      <button
        @click="openCreate"
        class="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700"
      >
        创建策略
      </button>
    </div>

    <!-- 策略列表 -->
    <div class="mt-8 bg-white rounded-lg shadow overflow-hidden">
      <table class="min-w-full">
        <thead class="bg-gray-50">
          <tr>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">名称</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">描述</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">创建时间</th>
            <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">操作</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-200">
          <tr v-if="loading">
            <td colspan="4" class="px-6 py-4 text-center text-gray-500">加载中...</td>
          </tr>
          <tr v-else-if="strategies.length === 0">
            <td colspan="4" class="px-6 py-4 text-center text-gray-500">暂无策略</td>
          </tr>
          <tr v-else v-for="strategy in strategies" :key="strategy.id" class="hover:bg-gray-50">
            <td class="px-6 py-4 whitespace-nowrap font-medium text-gray-900">
              {{ strategy.name }}
            </td>
            <td class="px-6 py-4 text-gray-600">{{ strategy.description || '-' }}</td>
            <td class="px-6 py-4 whitespace-nowrap text-gray-600">
              {{ new Date(strategy.created_at).toLocaleString() }}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-right">
              <button
                @click="editStrategy(strategy.id)"
                class="text-blue-600 hover:text-blue-800 mr-4"
              >
                编辑
              </button>
              <button
                @click="deleteStrategy(strategy.id)"
                class="text-red-600 hover:text-red-800"
              >
                删除
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 策略编辑器对话框 -->
    <div
      v-if="showEditor"
      class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
    >
      <div class="bg-white rounded-lg shadow-xl w-full max-w-4xl max-h-[90vh] overflow-hidden">
        <div class="px-6 py-4 border-b flex justify-between items-center">
          <h2 class="text-xl font-semibold">
            {{ editingId ? '编辑策略' : '创建策略' }}
          </h2>
          <button @click="showEditor = false" class="text-gray-400 hover:text-gray-600">
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div class="p-6">
          <div class="space-y-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">策略名称</label>
              <input
                v-model="form.name"
                type="text"
                class="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="例如：双均线策略"
              />
            </div>

            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">描述</label>
              <textarea
                v-model="form.description"
                rows="2"
                class="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="简要描述策略逻辑"
              ></textarea>
            </div>

            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">策略代码</label>
              <textarea
                v-model="form.code"
                rows="20"
                class="w-full px-3 py-2 border rounded-lg font-mono text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="编写策略代码"
              ></textarea>
            </div>
          </div>
        </div>

        <div class="px-6 py-4 bg-gray-50 flex justify-end space-x-3">
          <button
            @click="showEditor = false"
            class="px-4 py-2 border rounded-lg hover:bg-gray-100"
          >
            取消
          </button>
          <button
            @click="editingId ? updateStrategy() : createStrategy()"
            class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            {{ editingId ? '更新' : '创建' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

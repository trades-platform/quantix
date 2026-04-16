import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useStrategiesStore = defineStore('strategies', () => {
  const strategies = ref([])
  const loading = ref(false)
  const saving = ref(false)
  const error = ref(null)

  const hasStrategies = computed(() => strategies.value.length > 0)

  const fetchStrategies = async (api) => {
    loading.value = true
    error.value = null
    try {
      const response = await api.list()
      strategies.value = response.data
    } catch (err) {
      error.value = err.message || '获取策略列表失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  const createStrategy = async (api, data) => {
    saving.value = true
    error.value = null
    try {
      const response = await api.create(data)
      strategies.value.push(response.data)
      return response.data
    } catch (err) {
      error.value = err.message || '创建策略失败'
      throw err
    } finally {
      saving.value = false
    }
  }

  const updateStrategy = async (api, id, data) => {
    saving.value = true
    error.value = null
    try {
      const response = await api.update(id, data)
      const index = strategies.value.findIndex(s => s.id === id)
      if (index !== -1) {
        strategies.value[index] = response.data
      }
      return response.data
    } catch (err) {
      error.value = err.message || '更新策略失败'
      throw err
    } finally {
      saving.value = false
    }
  }

  const deleteStrategy = async (api, id) => {
    loading.value = true
    error.value = null
    try {
      await api.delete(id)
      strategies.value = strategies.value.filter(s => s.id !== id)
    } catch (err) {
      error.value = err.message || '删除策略失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  const getStrategyById = (id) => {
    return strategies.value.find(s => s.id === id)
  }

  return {
    strategies,
    loading,
    error,
    hasStrategies,
    fetchStrategies,
    createStrategy,
    updateStrategy,
    deleteStrategy,
    getStrategyById
  }
})

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useBacktestStore = defineStore('backtest', () => {
  const currentBacktest = ref(null)
  const trades = ref([])
  const backtests = ref([])
  const loading = ref(false)
  const running = ref(false)
  const error = ref(null)

  const hasResults = computed(() => currentBacktest.value !== null)

  const fetchBacktest = async (api, id) => {
    loading.value = true
    error.value = null
    try {
      const response = await api.get(id)
      currentBacktest.value = response.data
      return response.data
    } catch (err) {
      error.value = err.message || '获取回测结果失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  const fetchTrades = async (api, id) => {
    loading.value = true
    error.value = null
    try {
      const response = await api.getTrades(id)
      trades.value = response.data
      return response.data
    } catch (err) {
      error.value = err.message || '获取交易明细失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  const runBacktest = async (api, data) => {
    running.value = true
    error.value = null
    try {
      const response = await api.create(data)
      currentBacktest.value = response.data
      return response.data
    } catch (err) {
      error.value = err.message || '运行回测失败'
      throw err
    } finally {
      running.value = false
    }
  }

  const clearResults = () => {
    currentBacktest.value = null
    trades.value = []
    error.value = null
  }

  return {
    currentBacktest,
    trades,
    backtests,
    loading,
    running,
    error,
    hasResults,
    fetchBacktest,
    fetchTrades,
    runBacktest,
    clearResults
  }
})

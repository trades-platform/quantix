import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useDataStore = defineStore('data', () => {
  const symbols = ref([])
  const klineData = ref([])
  const loading = ref(false)
  const error = ref(null)
  const selectedSymbol = ref(null)

  const filteredSymbols = computed(() => {
    if (!symbols.value) return []
    return symbols.value
  })

  const hasData = computed(() => klineData.value.length > 0)

  const fetchSymbols = async (api) => {
    loading.value = true
    error.value = null
    try {
      const response = await api.getSymbols()
      symbols.value = response.data
      return response.data
    } catch (err) {
      error.value = err.message || '获取标的列表失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  const fetchKline = async (api, params) => {
    loading.value = true
    error.value = null
    try {
      const response = await api.getKline(params)
      klineData.value = response.data.data ?? response.data
      selectedSymbol.value = params.symbol
      return response.data
    } catch (err) {
      error.value = err.message || '获取K线数据失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  const clearKlineData = () => {
    klineData.value = []
    selectedSymbol.value = null
  }

  const fetchSingleKline = async (api, params) => {
    loading.value = true
    error.value = null
    try {
      const response = await api.fetchKline(params)
      return response.data
    } catch (err) {
      error.value = err.message || '获取K线数据失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  const fetchBatchKline = async (api, params) => {
    loading.value = true
    error.value = null
    try {
      const response = await api.fetchKlineBatch(params)
      return response.data
    } catch (err) {
      error.value = err.message || '批量获取K线数据失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  return {
    symbols,
    klineData,
    loading,
    error,
    selectedSymbol,
    filteredSymbols,
    hasData,
    fetchSymbols,
    fetchKline,
    clearKlineData,
    fetchSingleKline,
    fetchBatchKline
  }
})

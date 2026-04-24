import axios from 'axios'
import { mockStrategies, mockSymbols, mockSymbolPools, generateMockKlineData, mockBacktestResult, mockTrades } from '../stores/mock'

const USE_MOCK = false

const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms))

// Mock API implementation
export const mockApi = {
  strategies: {
    list: async () => {
      await delay(300)
      return { data: mockStrategies }
    },
    get: async (id) => {
      await delay(200)
      const strategy = mockStrategies.find(s => s.id === id)
      if (!strategy) {
        throw new Error('Strategy not found')
      }
      return { data: strategy }
    },
    create: async (data) => {
      await delay(400)
      const newStrategy = {
        id: String(Date.now()),
        ...data,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      }
      mockStrategies.push(newStrategy)
      return { data: newStrategy }
    },
    update: async (id, data) => {
      await delay(400)
      const index = mockStrategies.findIndex(s => s.id === id)
      if (index === -1) {
        throw new Error('Strategy not found')
      }
      mockStrategies[index] = {
        ...mockStrategies[index],
        ...data,
        updated_at: new Date().toISOString()
      }
      return { data: mockStrategies[index] }
    },
    delete: async (id) => {
      await delay(300)
      const index = mockStrategies.findIndex(s => s.id === id)
      if (index === -1) {
        throw new Error('Strategy not found')
      }
      mockStrategies.splice(index, 1)
      return { data: { success: true } }
    }
  },
  backtest: {
    create: async (data) => {
      await delay(2000)
      const displayTarget = data.pool_name ? `@${data.pool_name}` : (data.symbol || data.symbols?.join(',') || mockBacktestResult.symbol)
      return {
        data: {
          ...mockBacktestResult,
          id: 'bt-' + Date.now(),
          symbol: displayTarget,
          start_date: data.start_date,
          end_date: data.end_date,
          initial_capital: data.initial_capital
        }
      }
    },
    get: async (id) => {
      await delay(500)
      return { data: mockBacktestResult }
    },
    getTrades: async (id) => {
      await delay(300)
      return { data: mockTrades }
    },
    delete: async (id) => {
      await delay(300)
      return { data: { success: true } }
    }
  },
  data: {
    getSymbols: async () => {
      await delay(300)
      return { data: mockSymbols }
    },
    getKline: async (params) => {
      await delay(500)
      const data = generateMockKlineData(params.symbol, 100)
      return { data }
    },
    fetchKline: async (data) => {
      await delay(1500)
      const count = Math.floor(Math.random() * 100) + 50
      return { data: { symbol: data.symbol, count, message: '数据获取成功' } }
    },
    fetchKlineBatch: async (data) => {
      await delay(3000)
      const results = data.symbols.map(symbol => ({
        symbol,
        count: Math.floor(Math.random() * 100) + 50,
        success: true
      }))
      return { data: { results, total: results.reduce((sum, r) => sum + r.count, 0) } }
    }
  },
  symbolPools: {
    list: async () => {
      await delay(300)
      return { data: mockSymbolPools }
    },
    get: async (name) => {
      await delay(200)
      const pool = mockSymbolPools.find((item) => item.name === name)
      if (!pool) {
        throw new Error('Symbol pool not found')
      }
      return { data: pool }
    },
    create: async (data) => {
      await delay(300)
      const newPool = {
        id: Date.now(),
        ...data,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      }
      mockSymbolPools.push(newPool)
      return { data: newPool }
    },
    update: async (name, data) => {
      await delay(300)
      const index = mockSymbolPools.findIndex((item) => item.name === name)
      if (index === -1) {
        throw new Error('Symbol pool not found')
      }
      mockSymbolPools[index] = {
        ...mockSymbolPools[index],
        ...data,
        updated_at: new Date().toISOString()
      }
      return { data: mockSymbolPools[index] }
    },
    delete: async (name) => {
      await delay(300)
      const index = mockSymbolPools.findIndex((item) => item.name === name)
      if (index === -1) {
        throw new Error('Symbol pool not found')
      }
      mockSymbolPools.splice(index, 1)
      return { data: { success: true } }
    }
  }
}

const api = axios.create({
  baseURL: '/api',
  timeout: 120000,
})

// Strategy API with fallback to mock
export const strategyApi = {
  list: () => USE_MOCK ? mockApi.strategies.list() : api.get('/strategies'),
  get: (id) => USE_MOCK ? mockApi.strategies.get(id) : api.get(`/strategies/${id}`),
  create: (data) => USE_MOCK ? mockApi.strategies.create(data) : api.post('/strategies', data),
  update: (id, data) => USE_MOCK ? mockApi.strategies.update(id, data) : api.put(`/strategies/${id}`, data),
  delete: (id) => USE_MOCK ? mockApi.strategies.delete(id) : api.delete(`/strategies/${id}`),
}

// Backtest API with fallback to mock
export const backtestApi = {
  create: (data) => USE_MOCK ? mockApi.backtest.create(data) : api.post('/backtests', data),
  get: (id) => USE_MOCK ? mockApi.backtest.get(id) : api.get(`/backtests/${id}`),
  getTrades: (id) => USE_MOCK ? mockApi.backtest.getTrades(id) : api.get(`/backtests/${id}/trades`),
  delete: (id) => USE_MOCK ? mockApi.backtest.delete(id) : api.delete(`/backtests/${id}`),
}

// Data API with fallback to mock
export const dataApi = {
  getSymbols: () => USE_MOCK ? mockApi.data.getSymbols() : api.get('/data/symbols'),
  getKline: (params) => USE_MOCK ? mockApi.data.getKline(params) : api.get('/data/kline', { params }),
  fetchKline: (data) => USE_MOCK ? mockApi.data.fetchKline(data) : api.post('/data/kline/fetch', data),
  fetchKlineBatch: (data) => USE_MOCK ? mockApi.data.fetchKlineBatch(data) : api.post('/data/kline/fetch-batch', data),
}

export const symbolPoolApi = {
  list: () => USE_MOCK ? mockApi.symbolPools.list() : api.get('/symbol-pools'),
  get: (name) => USE_MOCK ? mockApi.symbolPools.get(name) : api.get(`/symbol-pools/${name}`),
  create: (data) => USE_MOCK ? mockApi.symbolPools.create(data) : api.post('/symbol-pools', data),
  update: (name, data) => USE_MOCK ? mockApi.symbolPools.update(name, data) : api.put(`/symbol-pools/${name}`, data),
  delete: (name) => USE_MOCK ? mockApi.symbolPools.delete(name) : api.delete(`/symbol-pools/${name}`),
}

export default api

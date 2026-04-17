import axios from 'axios'
import { mockStrategies, mockSymbols, generateMockKlineData, mockBacktestResult, mockTrades } from '../stores/mock'

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
      return {
        data: {
          ...mockBacktestResult,
          id: 'bt-' + Date.now(),
          symbol: data.symbol,
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

export default api

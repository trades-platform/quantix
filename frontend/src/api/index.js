import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 10000,
})

// 策略相关 API
export const strategyApi = {
  list: () => api.get('/strategies'),
  get: (id) => api.get(`/strategies/${id}`),
  create: (data) => api.post('/strategies', data),
  update: (id, data) => api.put(`/strategies/${id}`, data),
  delete: (id) => api.delete(`/strategies/${id}`),
}

// 回测相关 API
export const backtestApi = {
  create: (data) => api.post('/backtests', data),
  get: (id) => api.get(`/backtests/${id}`),
  getTrades: (id) => api.get(`/backtests/${id}/trades`),
  delete: (id) => api.delete(`/backtests/${id}`),
}

// 数据相关 API
export const dataApi = {
  getSymbols: () => api.get('/data/symbols'),
  getKline: (params) => api.get('/data/kline', { params }),
  importKline: (data) => api.post('/data/kline/import', data),
}

export default api

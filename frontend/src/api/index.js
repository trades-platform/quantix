// Re-export from mock.js to use mock data during development
export { strategyApi, backtestApi, dataApi } from './mock.js'
import mockApi from './mock.js'
export const api = mockApi
export default api

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

// 后端端口：默认 9000，可被 VITE_BACKEND_PORT 环境变量覆盖
// （scripts/server.sh 启动前端时会按 --port 注入该变量）
const backendPort = process.env.VITE_BACKEND_PORT || '9000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue(), tailwindcss()],
  server: {
    host: '0.0.0.0',
    proxy: {
      '/api': {
        target: `http://localhost:${backendPort}`,
        changeOrigin: true,
      },
    },
  },
})

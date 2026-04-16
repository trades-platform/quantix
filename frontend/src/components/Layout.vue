<script setup>
import { RouterLink, useRoute } from 'vue-router'

const route = useRoute()

const navigation = [
  { name: '首页', href: '/', icon: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6' },
  { name: '策略管理', href: '/strategies', icon: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z' },
  { name: '回测配置', href: '/backtest', icon: 'M13 10V3L4 14h7v7l9-11h-7z' },
  { name: '回测结果', href: '/results', icon: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z' },
  { name: '数据管理', href: '/data', icon: 'M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4' },
]

const isActive = (href) => {
  if (href === '/') {
    return route.path === '/'
  }
  return route.path.startsWith(href)
}
</script>

<template>
  <div class="flex h-screen bg-gray-50">
    <!-- 侧边栏 -->
    <aside class="w-64 bg-gray-900 text-white flex flex-col">
      <div class="p-6 border-b border-gray-700">
        <h1 class="text-2xl font-bold">Quantix</h1>
        <p class="text-sm text-gray-400 mt-1">量化回测平台</p>
      </div>

      <nav class="flex-1 p-4">
        <ul class="space-y-2">
          <li v-for="item in navigation" :key="item.name">
            <RouterLink
              :to="item.href"
              class="flex items-center px-4 py-3 rounded-lg transition-colors"
              :class="isActive(item.href) ? 'bg-blue-600 text-white' : 'text-gray-300 hover:bg-gray-800'"
            >
              <svg class="w-5 h-5 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" :d="item.icon" />
              </svg>
              {{ item.name }}
            </RouterLink>
          </li>
        </ul>
      </nav>

      <div class="p-4 border-t border-gray-700">
        <div class="text-sm text-gray-400">
          <p>当前版本: v1.0.0</p>
        </div>
      </div>
    </aside>

    <!-- 主内容区 -->
    <main class="flex-1 overflow-auto">
      <RouterView />
    </main>
  </div>
</template>

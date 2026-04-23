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
  <div class="flex h-screen">
    <!-- 侧边栏 -->
    <aside class="w-64 bg-slate-900 text-white flex flex-col flex-shrink-0">
      <!-- Logo 区域 - 渐变色 -->
      <div class="px-6 py-5 bg-gradient-to-r from-blue-800 to-blue-600">
        <div class="flex items-center space-x-3">
          <div class="w-9 h-9 bg-white/20 rounded-lg flex items-center justify-center backdrop-blur-sm">
            <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
            </svg>
          </div>
          <div>
            <h1 class="text-xl font-bold tracking-wide">Quantix</h1>
            <p class="text-xs text-blue-200/80">量化回测平台</p>
          </div>
        </div>
      </div>

      <!-- 导航区域 -->
      <nav class="flex-1 px-3 py-4">
        <ul class="space-y-1">
          <li v-for="item in navigation" :key="item.name">
            <RouterLink
              :to="item.href"
              class="group relative flex items-center px-3 py-2.5 rounded-lg transition-all duration-200 ease-out"
              :class="isActive(item.href)
                ? 'bg-blue-600/20 text-blue-400'
                : 'text-slate-400 hover:bg-white/5 hover:text-slate-200'"
            >
              <!-- 左侧高亮条 -->
              <span
                class="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-r-full transition-all duration-200"
                :class="isActive(item.href) ? 'bg-blue-400 opacity-100' : 'bg-transparent opacity-0 group-hover:bg-slate-600 group-hover:opacity-100'"
              ></span>
              <svg class="w-5 h-5 mr-3 flex-shrink-0 transition-transform duration-200" :class="isActive(item.href) ? 'scale-110' : 'group-hover:scale-105'" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" :d="item.icon" />
              </svg>
              <span class="text-sm font-medium">{{ item.name }}</span>
            </RouterLink>
          </li>
        </ul>
      </nav>

      <!-- 底部版本信息 -->
      <div class="px-6 py-3 border-t border-slate-700/50">
        <p class="text-[11px] text-slate-500 tracking-wide">v1.0.0</p>
      </div>
    </aside>

    <!-- 主内容区 -->
    <main class="flex-1 overflow-auto bg-gradient-to-br from-slate-50 to-gray-100">
      <RouterView />
    </main>
  </div>
</template>

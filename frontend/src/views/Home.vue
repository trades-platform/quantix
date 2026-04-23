<script setup>
import { ref, onMounted } from 'vue'

const stats = ref([
  { label: '策略数量', value: 0, color: 'from-blue-500 to-blue-600', icon: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z' },
  { label: '回测任务', value: 0, color: 'from-emerald-500 to-emerald-600', icon: 'M13 10V3L4 14h7v7l9-11h-7z' },
  { label: '数据标的', value: 0, color: 'from-violet-500 to-violet-600', icon: 'M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4' },
])

const quickActions = [
  { name: '创建策略', desc: '编写和管理您的量化策略', href: '/strategies', icon: 'M12 4v16m8-8H4', color: 'text-blue-600 bg-blue-50' },
  { name: '运行回测', desc: '执行策略回测并查看结果', href: '/backtest', icon: 'M13 10V3L4 14h7v7l9-11h-7z', color: 'text-emerald-600 bg-emerald-50' },
  { name: '导入数据', desc: '获取和管理历史K线数据', href: '/data', icon: 'M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12', color: 'text-violet-600 bg-violet-50' },
  { name: '查看结果', desc: '浏览回测报告和绩效分析', href: '/results', icon: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z', color: 'text-amber-600 bg-amber-50' },
]

const steps = [
  { label: '导入数据', desc: '前往数据管理导入历史K线数据', href: '/data' },
  { label: '创建策略', desc: '在策略管理中编写您的量化策略', href: '/strategies' },
  { label: '运行回测', desc: '在回测配置中设置参数并运行', href: '/backtest' },
  { label: '查看报告', desc: '在回测结果中分析绩效表现', href: '/results' },
]

onMounted(() => {
  // TODO: 从后端获取统计数据
  stats.value[0].value = 3
  stats.value[1].value = 12
  stats.value[2].value = 5
})
</script>

<template>
  <div class="p-8">
    <!-- 页面标题 -->
    <div class="mb-8">
      <h1 class="text-3xl font-bold text-gray-900">仪表盘</h1>
      <div class="flex items-center mt-2">
        <div class="h-[3px] w-12 rounded-full bg-gradient-to-r from-blue-500 to-blue-600 mr-3"></div>
        <p class="text-gray-500">欢迎使用 Quantix 量化回测平台</p>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
      <div
        v-for="stat in stats"
        :key="stat.label"
        class="relative overflow-hidden rounded-xl bg-gradient-to-br p-6 text-white shadow-lg hover:shadow-xl hover:-translate-y-1 transition-all duration-300 ease-out cursor-default"
        :class="stat.color"
      >
        <!-- 背景装饰 -->
        <div class="absolute -right-4 -top-4 h-24 w-24 rounded-full bg-white/10"></div>
        <div class="absolute -right-2 -bottom-6 h-20 w-20 rounded-full bg-white/5"></div>
        <div class="relative">
          <div class="flex items-center justify-between">
            <p class="text-sm font-medium text-white/80">{{ stat.label }}</p>
            <svg class="w-8 h-8 text-white/30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" :d="stat.icon" />
            </svg>
          </div>
          <p class="text-4xl font-bold mt-3">{{ stat.value }}</p>
        </div>
      </div>
    </div>

    <!-- 快速操作 -->
    <div class="mt-8">
      <h2 class="text-lg font-semibold text-gray-900 mb-4">快速操作</h2>
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <RouterLink
          v-for="action in quickActions"
          :key="action.name"
          :to="action.href"
          class="group bg-white rounded-xl shadow-sm border border-gray-100 p-5 hover:shadow-md hover:border-blue-200 hover:-translate-y-0.5 transition-all duration-200 ease-out"
        >
          <div class="flex items-center space-x-3">
            <div class="w-10 h-10 rounded-lg flex items-center justify-center" :class="action.color">
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" :d="action.icon" />
              </svg>
            </div>
            <div>
              <h3 class="font-semibold text-gray-900 text-sm group-hover:text-blue-600 transition-colors">{{ action.name }}</h3>
              <p class="text-xs text-gray-500 mt-0.5">{{ action.desc }}</p>
            </div>
          </div>
        </RouterLink>
      </div>
    </div>

    <!-- 使用指南 - 时间线样式 -->
    <div class="mt-8 bg-white rounded-xl shadow-sm border border-gray-100 p-6">
      <h2 class="text-lg font-semibold text-gray-900 mb-6">快速开始</h2>
      <div class="relative">
        <!-- 连接线 -->
        <div class="absolute left-5 top-6 bottom-6 w-px bg-gradient-to-b from-blue-300 via-blue-300 to-transparent"></div>

        <div class="space-y-6">
          <div
            v-for="(step, index) in steps"
            :key="step.label"
            class="relative flex items-start"
          >
            <!-- 数字圆圈 -->
            <div class="relative z-10 flex-shrink-0 w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center shadow-sm">
              <span class="text-sm font-bold text-white">{{ index + 1 }}</span>
            </div>
            <!-- 内容 -->
            <div class="ml-4 pt-1">
              <RouterLink :to="step.href" class="font-semibold text-gray-900 hover:text-blue-600 transition-colors">
                {{ step.label }}
              </RouterLink>
              <p class="text-sm text-gray-500 mt-0.5">{{ step.desc }}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

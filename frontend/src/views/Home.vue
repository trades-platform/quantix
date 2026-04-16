<script setup>
import { ref, onMounted } from 'vue'

const stats = ref([
  { label: '策略数量', value: 0, color: 'bg-blue-500' },
  { label: '回测任务', value: 0, color: 'bg-green-500' },
  { label: '数据标的', value: 0, color: 'bg-purple-500' },
])

onMounted(() => {
  // TODO: 从后端获取统计数据
  stats.value[0].value = 3
  stats.value[1].value = 12
  stats.value[2].value = 5
})
</script>

<template>
  <div class="p-8">
    <h1 class="text-3xl font-bold text-gray-900">仪表盘</h1>
    <p class="mt-2 text-gray-600">欢迎使用 Quantix 量化回测平台</p>

    <!-- 统计卡片 -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mt-8">
      <div
        v-for="stat in stats"
        :key="stat.label"
        class="bg-white rounded-lg shadow p-6 border-l-4"
        :class="stat.color"
      >
        <p class="text-sm text-gray-600">{{ stat.label }}</p>
        <p class="text-3xl font-bold mt-2">{{ stat.value }}</p>
      </div>
    </div>

    <!-- 快速操作 -->
    <div class="mt-8">
      <h2 class="text-xl font-semibold text-gray-900 mb-4">快速操作</h2>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <RouterLink
          to="/strategies"
          class="bg-white p-6 rounded-lg shadow hover:shadow-md transition-shadow"
        >
          <h3 class="font-semibold text-gray-900">创建策略</h3>
          <p class="text-sm text-gray-600 mt-1">编写和管理您的量化策略</p>
        </RouterLink>
        <RouterLink
          to="/backtest"
          class="bg-white p-6 rounded-lg shadow hover:shadow-md transition-shadow"
        >
          <h3 class="font-semibold text-gray-900">运行回测</h3>
          <p class="text-sm text-gray-600 mt-1">执行策略回测并查看结果</p>
        </RouterLink>
      </div>
    </div>

    <!-- 使用指南 -->
    <div class="mt-8 bg-white rounded-lg shadow p-6">
      <h2 class="text-xl font-semibold text-gray-900 mb-4">快速开始</h2>
      <ol class="list-decimal list-inside space-y-2 text-gray-700">
        <li>前往 <RouterLink to="/data" class="text-blue-600 hover:underline">数据管理</RouterLink> 导入历史K线数据</li>
        <li>在 <RouterLink to="/strategies" class="text-blue-600 hover:underline">策略管理</RouterLink> 中创建您的策略</li>
        <li>在 <RouterLink to="/backtest" class="text-blue-600 hover:underline">回测配置</RouterLink> 中设置参数并运行回测</li>
        <li>在 <RouterLink to="/results" class="text-blue-600 hover:underline">回测结果</RouterLink> 中查看分析报告</li>
      </ol>
    </div>
  </div>
</template>

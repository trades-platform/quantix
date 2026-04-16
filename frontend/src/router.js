import { createRouter, createWebHistory } from 'vue-router'
import Layout from './components/Layout.vue'

const routes = [
  {
    path: '/',
    component: Layout,
    children: [
      {
        path: '',
        name: 'home',
        component: () => import('./views/Home.vue'),
      },
      {
        path: 'strategies',
        name: 'strategies',
        component: () => import('./views/Strategies.vue'),
      },
      {
        path: 'backtest',
        name: 'backtest',
        component: () => import('./views/Backtest.vue'),
      },
      {
        path: 'results',
        name: 'results',
        component: () => import('./views/Results.vue'),
      },
      {
        path: 'data',
        name: 'data',
        component: () => import('./views/Data.vue'),
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router

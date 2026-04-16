# Quantix 前端测试计划

## 测试概述

本文档定义了 Quantix 量化回测平台前端的测试策略、测试范围和具体测试用例。

### 技术栈
- **测试框架**: Vitest
- **组件测试**: @vue/test-utils
- **Mock 工具**: vi (Vitest 内置)
- **覆盖目标**: 代码覆盖率 ≥ 75%

## 测试范围

### 1. 组件测试 (Component Tests)

#### 1.1 基础组件 (`src/components/`)
- **HelloWorld**
  - 渲染正确性
  - Props 传递
  - 事件触发

#### 1.2 业务组件 (待实现)
- **StrategyForm** - 策略创建/编辑表单
- **StrategyList** - 策略列表展示
- **BacktestConfig** - 回测配置表单
- **BacktestResult** - 回测结果展示
- **KlineChart** - K线图表 (ECharts)
- **PerformanceChart** - 性能指标图表

### 2. 页面功能测试 (`src/views/`)

#### 2.1 Home 页面
- 页面渲染
- 内容展示

#### 2.2 待实现页面
- **StrategyManage** - 策略管理页面
- **BacktestPage** - 回测执行页面
- **DataManage** - 数据管理页面

### 3. API 调用测试 (`src/api/`)

#### 3.1 API 客户端
- 请求拦截
- 响应处理
- 错误处理
- 超时处理

#### 3.2 API 函数 (待实现)
- `createStrategy()`
- `getStrategies()`
- `getStrategy(id)`
- `updateStrategy(id, data)`
- `deleteStrategy(id)`
- `runBacktest(config)`
- `getBacktestResult(id)`
- `getKlineData(params)`

### 4. 路由测试 (`src/router.js`)

- 路由配置正确性
- 路由跳转
- 路由守卫 (如实现)

### 5. 状态管理测试 (如实现 Pinia)

- Store 状态更新
- Actions 执行
- Getters 计算

## 测试策略

### 1. 测试组织结构
```
frontend/
├── tests/
│   ├── unit/              # 单元测试
│   │   ├── components/    # 组件测试
│   │   │   ├── HelloWorld.spec.js
│   │   │   ├── StrategyForm.spec.js
│   │   │   └── BacktestResult.spec.js
│   │   ├── api/           # API 测试
│   │   │   └── index.spec.js
│   │   └── utils/         # 工具函数测试
│   ├── integration/       # 集成测试
│   │   └── pages/         # 页面测试
│   │       └── Home.spec.js
│   └── setup.js           # 测试配置
└── vitest.config.js       # Vitest 配置
```

### 2. 测试配置 (vitest.config.js)
```js
export default defineConfig({
  test: {
    environment: 'jsdom',
    globals: true,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html'],
      exclude: ['node_modules/', 'tests/']
    }
  }
})
```

### 3. Mock 策略
- **API Mock**: 使用 `vi.mock()` 模拟 axios 请求
- **路由 Mock**: 使用 `vue-router` 的测试工具
- **ECharts Mock**: 简化图表组件测试

### 4. 测试工具
- **@vue/test-utils**: 组件挂载和交互
- **vi.spyOn()**: 监听函数调用
- **vi.fn()**: Mock 函数

## 具体测试用例

### 组件测试用例清单

#### HelloWorld 组件
| 用例 ID | 描述 | 预期结果 |
|---------|------|----------|
| TC-COMP-001 | 组件正常渲染 | 包含正确文本内容 |
| TC-COMP-002 | 接收 props | Props 正确传递到模板 |

#### StrategyForm 组件 (待实现)
| 用例 ID | 描述 | 预期结果 |
|---------|------|----------|
| TC-COMP-101 | 渲染表单字段 | 所有字段正确显示 |
| TC-COMP-102 | 表单验证 | 空字段显示错误 |
| TC-COMP-103 | 提交有效数据 | 触发 submit 事件 |
| TC-COMP-104 | 编辑模式预填 | 数据正确回显 |

#### KlineChart 组件 (待实现)
| 用例 ID | 描述 | 预期结果 |
|---------|------|----------|
| TC-COMP-201 | 图表初始化 | ECharts 实例创建 |
| TC-COMP-202 | 数据更新 | 图表正确更新 |
| TC-COMP-203 | 空数据处理 | 显示占位内容 |

### API 测试用例清单

#### API 客户端
| 用例 ID | 描述 | 预期结果 |
|---------|------|----------|
| TC-API-101 | GET 请求成功 | 返回正确数据 |
| TC-API-102 | POST 请求成功 | 返回创建数据 |
| TC-API-103 | 网络错误处理 | 返回错误信息 |
| TC-API-104 | 请求超时处理 | 触发超时逻辑 |

### 页面测试用例清单

#### Home 页面
| 用例 ID | 描述 | 预期结果 |
|---------|------|----------|
| TC-PAGE-001 | 页面渲染 | 显示标题和描述 |
| TC-PAGE-002 | 路由访问 | '/' 路由正确加载 |

#### StrategyManage 页面 (待实现)
| 用例 ID | 描述 | 预期结果 |
|---------|------|----------|
| TC-PAGE-101 | 加载策略列表 | 显示所有策略 |
| TC-PAGE-102 | 创建新策略 | 表单显示并提交 |
| TC-PAGE-103 | 编辑策略 | 表单预填数据 |
| TC-PAGE-104 | 删除策略 | 确认后删除 |

## 测试数据

### Fixtures
- **mockStrategies**: 模拟策略数据
- **mockBacktestResult**: 模拟回测结果
- **mockKlineData**: 模拟 K线数据

### Mock 响应示例
```js
const mockStrategies = [
  { id: 1, name: 'MA策略', description: '均线策略', code: '...' },
  { id: 2, name: '突破策略', description: '突破策略', code: '...' }
]
```

## 测试执行

### 本地运行
```bash
# 运行所有测试
pnpm test

# 运行特定文件
pnpm test HelloWorld.spec.js

# 监听模式
pnpm test:watch

# 覆盖率报告
pnpm test:coverage

# UI 模式
pnpm test:ui
```

### package.json 脚本配置
```json
{
  "scripts": {
    "test": "vitest",
    "test:watch": "vitest --watch",
    "test:coverage": "vitest --coverage",
    "test:ui": "vitest --ui"
  }
}
```

## E2E 测试 (可选)

如需端到端测试，可考虑：
- **Playwright**: 跨浏览器 E2E 测试
- **Cypress**: 完整的 E2E 测试框架

### E2E 测试场景
1. 用户登录 (如实现)
2. 创建并执行策略
3. 查看回测结果
4. 数据导入流程

## 测试完成标准

1. 所有组件测试通过
2. API 调用测试覆盖所有接口
3. 代码覆盖率 ≥ 75%
4. 关键用户流程测试通过

## 风险与注意事项

1. **异步测试**: 正确处理 async/await 和 Promise
2. **组件更新**: 确保等待 DOM 更新完成
3. **ECharts**: 图表组件测试需要特殊处理
4. **路由测试**: 使用 Vue Router 的测试工具

## 后续优化

1. 添加视觉回归测试
2. 添加性能测试
3. 添加可访问性测试
4. 集成 E2E 测试到 CI/CD

## 参考资源

- [Vitest 官方文档](https://vitest.dev/)
- [Vue Test Utils](https://test-utils.vuejs.org/)
- [Vue 3 测试指南](https://vuejs.org/guide/scaling-up/testing.html)

# Quantix 量化回测平台架构设计

## 1. 系统整体架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Quantix Platform                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                        Frontend (Vue 3)                                  │ │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐        │ │
│  │  │  Strategy  │  │  Backtest  │  │   Result   │  │    Data    │        │ │
│  │  │  Manager   │  │   Runner   │  │  Analysis  │  │  Manager   │        │ │
│  │  └────────────┘  └────────────┘  └────────────┘  └────────────┘        │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                    │                                          │
│                                    │ REST API                                  │
│                                    ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                      Backend (FastAPI)                                   │ │
│  │  ┌────────────────────────────────────────────────────────────────────┐ │ │
│  │  │  API Layer (router.py)                                             │ │ │
│  │  │  - Strategy API                                                    │ │ │
│  │  │  - Backtest API                                                    │ │ │
│  │  │  - Data API                                                        │ │ │
│  │  └────────────────────────────────────────────────────────────────────┘ │ │
│  │                                    │                                      │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │ │
│  │  │   Engine     │  │   Models     │  │  Database    │                  │ │
│  │  │   Layer      │  │   Layer      │  │   Layer      │                  │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘                  │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 2. 后端模块设计

### 2.1 目录结构

```
backend/
├── __init__.py
├── main.py                 # FastAPI 应用入口
├── api/                    # API 层
│   ├── __init__.py
│   ├── router.py           # 路由注册
│   ├── strategies.py       # 策略相关 API
│   ├── backtests.py        # 回测相关 API
│   └── data.py             # 数据相关 API
├── engine/                 # 引擎层
│   ├── __init__.py
│   ├── backtest.py         # 回测引擎核心
│   ├── executor.py         # 策略执行器
│   └── metrics.py          # 性能指标计算
├── models/                 # 模型层（SQLAlchemy）
│   ├── __init__.py
│   ├── strategy.py         # 策略模型
│   ├── backtest.py         # 回测结果模型
│   └── kline.py            # K线数据模型
├── db/                     # 数据层
│   ├── __init__.py
│   ├── sqlite.py           # SQLite 连接（业务数据）
│   └── lancedb.py          # LanceDB 连接（K线数据）
└── cli/                    # CLI 命令
    ├── __init__.py
    └── app.py              # Typer 应用
```

### 2.2 API 层设计

#### 2.2.1 策略管理 API (`/api/strategies`)

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/strategies` | 获取策略列表 |
| POST | `/api/strategies` | 创建策略 |
| GET | `/api/strategies/{id}` | 获取策略详情 |
| PUT | `/api/strategies/{id}` | 更新策略 |
| DELETE | `/api/strategies/{id}` | 删除策略 |

**策略数据结构**:
```json
{
  "id": 1,
  "name": "双均线策略",
  "description": "5日/20日均线交叉",
  "code": "def initialize(context):\n    context.short_period = 5\n    context.long_period = 20\n\ndef handle_bar(context, bar):\n    ...",
  "created_at": "2026-01-01T00:00:00Z",
  "updated_at": "2026-01-01T00:00:00Z"
}
```

#### 2.2.2 回测 API (`/api/backtests`)

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/backtests` | 创建回测任务 |
| GET | `/api/backtests/{id}` | 获取回测结果 |
| GET | `/api/backtests/{id}/trades` | 获取交易明细 |
| DELETE | `/api/backtests/{id}` | 删除回测结果 |

**回测请求结构**:
```json
{
  "strategy_id": 1,
  "symbol": "600000.SH",
  "start_date": "2024-01-01",
  "end_date": "2024-12-31",
  "initial_capital": 1000000,
  "commission": 0.0003
}
```

**回测结果结构**:
```json
{
  "id": 1,
  "status": "completed",
  "metrics": {
    "total_return": 0.25,
    "annual_return": 0.25,
    "sharpe_ratio": 1.5,
    "max_drawdown": -0.15,
    "win_rate": 0.6
  },
  "equity_curve": [...],
  "created_at": "2026-01-01T00:00:00Z"
}
```

#### 2.2.3 数据管理 API (`/api/data`)

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/data/symbols` | 获取可用标的列表 |
| GET | `/api/data/kline` | 获取K线数据 |
| POST | `/api/data/kline/import` | 导入K线数据 |

### 2.3 引擎层设计

#### 2.3.1 回测引擎核心 (`engine/backtest.py`)

```python
class BacktestEngine:
    def __init__(self, strategy, data, params):
        self.strategy = strategy
        self.data = data
        self.params = params
        self.portfolio = Portfolio(initial_capital=params.initial_capital)
        self.records = []

    def run(self):
        # 1. 初始化策略
        self.strategy.initialize(self.context)

        # 2. 逐根K线回放
        for bar in self.data:
            # 更新行情
            self.context.update(bar)

            # 调用策略
            orders = self.strategy.handle_bar(self.context)

            # 执行订单
            self._execute_orders(orders)

            # 记录状态
            self._record_state()

        # 3. 计算绩效
        return self._calculate_metrics()
```

#### 2.3.2 策略接口

```python
class Strategy:
    def initialize(self, context):
        """策略初始化"""
        pass

    def handle_bar(self, context):
        """处理单根K线，返回订单列表"""
        return []
```

### 2.4 数据模型设计

#### 2.4.1 SQLite 表结构

**strategies 表** (策略配置):
```sql
CREATE TABLE strategies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    code TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**backtests 表** (回测结果):
```sql
CREATE TABLE backtests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id INTEGER NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    initial_capital DECIMAL(15,2) NOT NULL,
    commission DECIMAL(8,4) NOT NULL,
    status VARCHAR(20) NOT NULL,
    total_return DECIMAL(10,4),
    annual_return DECIMAL(10,4),
    sharpe_ratio DECIMAL(10,4),
    max_drawdown DECIMAL(10,4),
    win_rate DECIMAL(10,4),
    equity_curve TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (strategy_id) REFERENCES strategies(id)
);
```

**trades 表** (交易明细):
```sql
CREATE TABLE trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    backtest_id INTEGER NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    price DECIMAL(15,2) NOT NULL,
    quantity INTEGER NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    FOREIGN KEY (backtest_id) REFERENCES backtests(id)
);
```

#### 2.4.2 LanceDB 数据结构

K线数据存储在 LanceDB，每个标的对应一个表：

```
表名: kline_{symbol}
Schema:
- timestamp: datetime (主键)
- open: float
- high: float
- low: float
- close: float
- volume: int64
- amount: float (可选，成交额)
```

## 3. 前端设计

### 3.1 目录结构

```
frontend/src/
├── main.js                 # 应用入口
├── App.vue                 # 根组件
├── router.js               # 路由配置
├── api/                    # API 调用封装
│   └── index.js
├── views/                  # 页面组件
│   ├── Home.vue            # 首页
│   ├── Strategies.vue      # 策略管理
│   ├── Backtest.vue        # 回测配置
│   └── Results.vue         # 结果分析
├── components/             # 通用组件
│   ├── CodeEditor.vue      # 代码编辑器
│   ├── KlineChart.vue      # K线图表
│   ├── EquityCurve.vue     # 净值曲线
│   └── TradeTable.vue      # 交易明细表
└── style.css               # 全局样式
```

### 3.2 页面设计

#### 3.2.1 策略管理页面 (`Strategies.vue`)

- 策略列表展示（表格）
- 新建/编辑/删除策略
- 代码编辑器（Monaco Editor 或 textarea）
- 策略参数配置

#### 3.2.2 回测配置页面 (`Backtest.vue`)

- 选择策略
- 选择标的
- 配置日期范围
- 配置初始资金、手续费等参数
- 启动回测按钮

#### 3.2.3 结果分析页面 (`Results.vue`)

- 性能指标卡片（收益率、夏普比率、最大回撤等）
- 净值曲线图（ECharts）
- 交易明细表
- K线图表叠加买卖点

### 3.3 组件设计

所有组件使用 Composition API + `<script setup>`:

```vue
<script setup>
import { ref, computed, onMounted } from 'vue'

// 响应式状态
const loading = ref(false)
const data = ref([])

// 计算属性
const total = computed(() => data.value.length)

// 生命周期
onMounted(() => {
  fetchData()
})
</script>

<template>
  <div class="p-4">
    <!-- 模板内容 -->
  </div>
</template>
```

## 4. 实现步骤

### 4.1 后端实现步骤

#### 阶段一：数据层和模型层
1. 完善 SQLite 模型（backtest.py、trade.py）
2. 实现 LanceDB K线数据导入和查询
3. 编写数据库初始化脚本

#### 阶段二：引擎层
1. 实现回测引擎核心逻辑
2. 实现策略执行器
3. 实现性能指标计算
4. 编写单元测试

#### 阶段三：API 层
1. 实现策略管理 API
2. 实现回测 API
3. 实现数据管理 API
4. 添加 CORS 支持

#### 阶段四：CLI 增强
1. 添加数据导入命令
2. 添加回测命令

### 4.2 前端实现步骤

#### 阶段一：基础框架
1. 配置路由和布局
2. 创建页面框架
3. 封装 API 调用

#### 阶段二：策略管理
1. 实现策略列表页面
2. 实现策略创建/编辑表单
3. 集成代码编辑器

#### 阶段三：回测功能
1. 实现回测配置页面
2. 实现回测结果展示
3. 集成 ECharts 图表

#### 阶段四：数据管理
1. 实现数据导入功能
2. 实现K线预览

### 4.3 集成测试

1. 前后端联调
2. E2E 测试
3. 性能测试

## 5. 技术要点

### 5.1 后端

- 使用 FastAPI 异步特性提升并发性能
- SQLAlchemy ORM 进行数据库操作
- Pandas 处理K线数据
- LanceDB 高效存储和查询时序数据

### 5.2 前端

- Vue 3 Composition API
- Vite 快速开发构建
- Tailwind CSS 实用优先样式
- ECharts 专业金融图表
- Axios HTTP 客户端

### 5.3 部署

- 前端构建后由 FastAPI 静态文件托管
- 单进程部署，简化运维
- 使用 uvicorn ASGI 服务器

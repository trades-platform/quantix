# Quantix 测试计划

## 测试概述

| 指标 | 后端 | 前端 |
|------|------|------|
| 测试框架 | pytest | Vitest |
| HTTP 客户端 | httpx / FastAPI TestClient | @vue/test-utils |
| 覆盖目标 | >= 80% | >= 75% |

## 后端测试

### 测试范围

- **数据库模型** — Strategy、Backtest、Trade 的 CRUD、关系完整性、级联删除
- **数据库连接** — SQLite 会话管理、init_db、事务回滚；LanceDB 连接与查询
- **回测引擎** — 策略执行、数据处理、性能指标、错误处理
- **API 端点** — 策略管理 CRUD、回测执行、K线数据查询与导入
- **CLI** — serve、initdb

### 测试用例清单

| 模块 | 用例数 | 状态 |
|------|--------|------|
| 数据库模型 | 21 | pass |
| SQLite 连接 | 5 | pass |
| LanceDB 连接 | 6 | pass |
| 回测引擎 | 10 | pass |
| API 集成 | 35 | pass |
| CLI | 7 | pass |
| **合计** | **86** | **all pass** |

### 覆盖率

| 模块 | 覆盖率 |
|------|--------|
| backend/api/ | 79%-100% |
| backend/engine/ | 80%-97% |
| backend/models/ | 100% |
| backend/cli/ | 24% |
| **总计** | **77%** |

### 执行

```bash
pytest                    # 运行全部
pytest tests/test_api/    # 单模块
pytest --cov=backend --cov-report=html  # 带覆盖率
```

## 前端测试

### 测试范围

- **组件测试** — CodeEditor、StrategyForm、KlineChart、BacktestResult
- **页面测试** — Home、Strategies、Backtest、DataManage
- **API 调用** — 请求/响应处理、错误处理、超时
- **路由** — 配置正确性、跳转、守卫
- **状态管理** — Pinia store actions/getters

### Mock 策略

- API: `vi.mock()` 模拟 axios
- 路由: vue-router 测试工具
- ECharts: 简化图表组件测试

### 执行

```bash
pnpm test              # 运行全部
pnpm test:watch        # 监听模式
pnpm test:coverage     # 覆盖率报告
```

## CI/CD

- PR 自动运行测试，合并前要求全部通过
- 后端覆盖率门槛 >= 75%

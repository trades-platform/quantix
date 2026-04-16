# Quantix 后端测试计划

## 测试概述

本文档定义了 Quantix 量化回测平台后端的测试策略、测试范围和具体测试用例。

### 技术栈
- **测试框架**: pytest
- **HTTP 客户端**: httpx / FastAPI TestClient
- **数据库**: SQLite (测试时使用内存数据库)
- **覆盖目标**: 代码覆盖率 ≥ 80%

## 测试范围

### 1. 单元测试 (Unit Tests)

#### 1.1 数据库模型测试 (`backend/models/`)
- **Strategy 模型**
  - 模型字段验证
  - 关系完整性
  - 约束检查

#### 1.2 数据库连接测试 (`backend/db/`)
- **SQLite 连接**
  - 连接建立和关闭
  - 会话管理
  - 数据库初始化 (`init_db`)
  - 事务处理

- **LanceDB 连接**
  - K线数据库连接
  - 数据库路径创建
  - 连接池管理

#### 1.3 回测引擎测试 (`backend/engine/`)
- **BacktestEngine**
  - 策略执行逻辑
  - 数据处理正确性
  - 性能指标计算
  - 错误处理

### 2. API 集成测试 (`backend/api/`)

#### 2.1 健康检查端点
```
GET /api/health
```
- 返回 200 状态码
- 返回正确的 JSON 响应

#### 2.2 策略管理端点 (待实现)
```
POST   /api/strategies          # 创建策略
GET    /api/strategies          # 获取策略列表
GET    /api/strategies/{id}     # 获取单个策略
PUT    /api/strategies/{id}     # 更新策略
DELETE /api/strategies/{id}     # 删除策略
```
- CRUD 操作正确性
- 输入验证
- 错误处理 (404, 400, 422)
- 数据持久化

#### 2.3 回测执行端点 (待实现)
```
POST /api/backtest             # 执行回测
GET  /api/backtest/{id}        # 获取回测结果
```
- 回测任务提交
- 异步执行状态跟踪
- 结果数据完整性

#### 2.4 K线数据端点 (待实现)
```
GET /api/kline/{symbol}?start={date}&end={date}  # 查询K线数据
POST /api/kline/import                              # 导入K线数据
```
- 数据查询正确性
- 日期范围过滤
- 数据导入功能

### 3. CLI 测试 (`backend/cli/`)

#### 3.1 serve 命令
- 服务启动
- 端口绑定
- 热重载功能

#### 3.2 initdb 命令
- 数据库初始化
- 表创建
- 重复初始化处理

## 测试策略

### 1. 测试组织结构
```
tests/
├── conftest.py              # pytest 配置和 fixtures
├── test_models/             # 模型测试
│   └── test_strategy.py
├── test_db/                 # 数据库测试
│   ├── test_sqlite.py
│   └── test_lancedb.py
├── test_engine/             # 回测引擎测试
│   └── test_backtest.py
├── test_api/                # API 测试
│   ├── test_health.py
│   ├── test_strategies.py
│   ├── test_backtest.py
│   └── test_kline.py
└── test_cli/                # CLI 测试
    └── test_app.py
```

### 2. Fixtures 定义
- **db_session**: 内存数据库会话
- **client**: FastAPI TestClient
- **sample_data**: 示例 K线数据
- **sample_strategy**: 示例策略配置

### 3. 测试数据管理
- 使用 factories 或 fixtures 创建测试数据
- 每个测试用例独立运行
- 测试后自动清理

### 4. Mock 策略
- LanceDB 使用内存或临时目录
- 外部 API 调用使用 mock
- 文件系统操作使用临时目录

## 具体测试用例

### API 测试用例清单

#### 健康检查 (test_health.py)
| 用例 ID | 描述 | 预期结果 |
|---------|------|----------|
| TC-API-001 | GET /api/health | 返回 {"status": "ok"}, 200 |

#### 策略管理 (test_strategies.py)
| 用例 ID | 描述 | 预期结果 |
|---------|------|----------|
| TC-API-201 | POST 创建有效策略 | 返回策略对象, 201 |
| TC-API-202 | POST 创建无效策略(缺少字段) | 返回验证错误, 422 |
| TC-API-203 | GET 获取策略列表 | 返回策略数组, 200 |
| TC-API-204 | GET 获取存在的策略 | 返回策略对象, 200 |
| TC-API-205 | GET 获取不存在的策略 | 返回 404 |
| TC-API-206 | PUT 更新策略 | 返回更新后的策略, 200 |
| TC-API-207 | DELETE 删除策略 | 返回 204 |

#### 回测执行 (test_backtest.py)
| 用例 ID | 描述 | 预期结果 |
|---------|------|----------|
| TC-API-301 | POST 有效回测请求 | 返回任务 ID, 202 |
| TC-API-302 | POST 缺少参数 | 返回验证错误, 422 |
| TC-API-303 | GET 查询回测结果 | 返回结果对象, 200 |
| TC-API-304 | GET 查询不存在的任务 | 返回 404 |

### 单元测试用例清单

#### 数据库 (test_sqlite.py)
| 用例 ID | 描述 | 预期结果 |
|---------|------|----------|
| TC-DB-001 | init_db 创建所有表 | 表成功创建 |
| TC-DB-002 | Session 上下文管理 | 会话正确关闭 |
| TC-DB-003 | 事务回滚 | 错误时数据不持久化 |

#### 回测引擎 (test_backtest.py)
| 用例 ID | 描述 | 预期结果 |
|---------|------|----------|
| TC-ENG-001 | 执行简单策略 | 返回正确结果 |
| TC-ENG-002 | 空数据处理 | 返回空结果 |
| TC-ENG-003 | 无效策略代码 | 抛出适当异常 |
| TC-ENG-004 | 性能指标计算 | 指标值正确 |

## 测试执行

### 本地运行
```bash
# 运行所有测试
pytest

# 运行特定模块
pytest tests/test_api/

# 带覆盖率报告
pytest --cov=backend --cov-report=html

# 带详细输出
pytest -v
```

### CI/CD 集成
- 每次 PR 自动运行测试
- 合并前要求测试通过
- 覆盖率门槛: ≥ 80%

## 测试完成标准

1. 所有测试用例通过
2. 代码覆盖率 ≥ 80%
3. 无关键 bug 未修复
4. 性能测试通过 (如适用)

## 风险与注意事项

1. **数据库隔离**: 测试使用内存数据库，避免影响开发数据
2. **异步测试**: 回测任务需要测试异步执行逻辑
3. **清理**: 确保 LanceDB 临时数据正确清理
4. **时区**: 日期处理注意时区问题

## 后续优化

1. 添加性能测试
2. 添加负载测试
3. 添加端到端测试
4. 集成测试环境自动化

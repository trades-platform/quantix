# Quantix - 量化回测平台

## 项目概述

量化回测平台，支持 Web 可视化和命令行两种使用方式。

## 技术栈

### 回测引擎
- **语言**: Python
- **数据处理**: pandas + numpy

### 后端
- **API 框架**: FastAPI
- **ORM**: SQLAlchemy

### 数据存储
- **K线数据库**: LanceDB - 专门存储历史K线数据，支持数据入库和查询
- **业务数据库**: SQLite - 存储策略配置、回测结果、用户数据等

### 前端
- **框架**: Vue 3
- **构建工具**: Vite
- **样式**: Tailwind CSS
- **图表库**: ECharts (vue-echarts)

### 命令行
- **CLI 框架**: typer

### 前后端通信
- **协议**: REST API

## 环境要求

- Python 3.12
- uv (Python 包管理，安装在 .venv 内)
- pnpm (前端包管理)

## 开发

### 启动后端（开发模式，热重载）

```bash
source .venv/bin/activate
uvicorn backend.main:app --host 0.0.0.0 --reload
```

### 启动前端（开发模式，热更新）

```bash
cd frontend && pnpm dev
```

开发时前端和后端分别启动，前端 dev server 代理 API 请求到后端。

## 部署

前端构建后由后端托管，只需启动一个进程：

```bash
# 1. 构建前端
cd frontend && pnpm build

# 2. 启动服务（默认监听 0.0.0.0:8000）
source ../.venv/bin/activate
quantix serve
# 或指定端口
quantix serve --port 3000
```

访问 `http://<host>:8000` 即可同时使用前端页面和 API。

## CLI 回测约定

使用 `quantix backtest run-file` 回测时，推荐以下默认参数：

| 参数 | 默认值 | 说明 |
|---|---|---|
| `start_date` | `1970-01-01` | 从最早可用数据开始 |
| `end_date` | 当前日期 | 回测到今天 |
| `--commission` | `0.000085` | 万分之 0.85（ETF 典型费率） |
| `--slippage` | 按标的流动性 | 高流动性 ETF 0.03%~0.05%，中等 0.05%~0.08% |
| `--period` | `1D` / `15min` 等 | 按策略需求选择 |
| `--adjust` | `hfq` | 后复权 |

示例：

```bash
quantix backtest run-file strategies/bollinger_reversion.py 159869.SZ 1970-01-01 2026-04-22 --period 15min --adjust hfq --commission 0.000085 --slippage 0.0003
```

## Git 提交规则

- 用英文描述
- 每次提交必须带 `Signed-off-by` trailer（`git commit -s`）
- 提交信息中不得包含 Claude Code、Copilot 等第三方工具的标记（如 `Generated with`、`Co-Authored-By` 等）

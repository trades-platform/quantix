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

## Git 提交规则

- 每次提交必须带 `Signed-off-by` trailer（`git commit -s`）
- 提交信息中不得包含 Claude Code、Copilot 等第三方工具的标记（如 `Generated with`、`Co-Authored-By` 等）

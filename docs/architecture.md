# Quantix 量化回测平台架构设计

## 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (Vue 3)                         │
│  Strategy Manager │ Backtest Runner │ Result Analysis │ Data     │
├──────────────────────────────────┬──────────────────────────────┤
│           REST API               │
├──────────────────────────────────┼──────────────────────────────┤
│                         Backend (FastAPI)                       │
│  API Layer (router) ─ Engine ─ Models ─ Database                │
├──────────────────────────────────┼──────────────────────────────┤
│                         CLI (Typer)                            │
└──────────────────────────────────┴──────────────────────────────┘
```

## 技术栈

### 回测引擎
- Python 3.12 + pandas + numpy

### 后端
- FastAPI + SQLAlchemy + uvicorn
- SQLite (业务数据) + LanceDB (K线数据)
- Typer (CLI)

### 前端
- Vue 3 + Vite + Tailwind CSS
- CodeMirror 6 (代码编辑器)
- ECharts / vue-echarts (图表)
- Pinia (状态管理)

### 部署
- 前端构建后由 FastAPI 托管，单进程部署
- SPA fallback：非 API、非静态资源的 GET 请求返回 index.html

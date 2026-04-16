from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api.router import add_cors_middleware, api_router

app = FastAPI(title="Quantix", description="量化回测平台")

# 添加 CORS 支持
add_cors_middleware(app)

app.include_router(api_router, prefix="/api")

# 托管前端构建产物
FRONTEND_DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")

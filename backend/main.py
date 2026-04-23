from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.api.router import add_cors_middleware, api_router
from backend.db import init_db


@asynccontextmanager
async def lifespan(app):
    init_db()
    yield


app = FastAPI(title="Quantix", description="量化回测平台", lifespan=lifespan)

# 添加 CORS 支持
add_cors_middleware(app)

app.include_router(api_router, prefix="/api")

# 托管前端构建产物（SPA fallback）
FRONTEND_DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if FRONTEND_DIST.is_dir():
    @app.get("/{full_path:path}")
    async def serve_spa(request: Request, full_path: str):
        file = (FRONTEND_DIST / full_path).resolve()
        if str(file).startswith(str(FRONTEND_DIST.resolve())) and file.is_file():
            return FileResponse(file)
        return FileResponse(FRONTEND_DIST / "index.html")

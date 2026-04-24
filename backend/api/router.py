from fastapi import APIRouter
from fastapi.middleware.cors import CORSMiddleware

from backend.api.backtests import router as backtests_router
from backend.api.charts import router as charts_router
from backend.api.data import router as data_router
from backend.api.strategies import router as strategies_router

api_router = APIRouter()

# CORS 中间件配置
def add_cors_middleware(app):
    """添加 CORS 支持"""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@api_router.get("/health")
def health_check():
    return {"status": "ok"}


# 注册子路由
api_router.include_router(strategies_router)
api_router.include_router(backtests_router)
api_router.include_router(charts_router)
api_router.include_router(data_router)

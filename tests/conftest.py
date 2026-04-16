"""pytest 配置和共享 fixtures"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.db.sqlite import engine, SessionLocal
from backend.main import app
from backend.models.backtest import Base


@pytest.fixture(scope="function")
def db_session():
    """创建测试用的内存数据库会话"""
    # 使用临时文件作为测试数据库
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db_path = Path(tmpdir) / "test.db"

        # 创建测试引擎
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        test_engine = create_engine(f"sqlite:///{test_db_path}", echo=False)
        TestingSessionLocal = sessionmaker(bind=test_engine)

        # 创建所有表
        Base.metadata.create_all(test_engine)

        # 创建会话
        session = TestingSessionLocal()

        yield session

        # 清理
        session.close()
        test_engine.dispose()


@pytest.fixture(scope="function")
def client(db_session):
    """创建测试用的 FastAPI TestClient"""

    def override_session():
        return db_session

    # 使用 monkey patch 来覆盖 SessionLocal
    import backend.db.sqlite
    import backend.api.strategies
    import backend.api.backtests
    import backend.db

    original_session = backend.db.sqlite.SessionLocal

    # 覆盖所有模块的 SessionLocal
    backend.db.sqlite.SessionLocal = override_session
    backend.api.strategies.SessionLocal = override_session
    backend.api.backtests.SessionLocal = override_session
    backend.db.SessionLocal = override_session

    # 创建测试客户端
    test_client = TestClient(app)

    yield test_client

    # 恢复原始 SessionLocal
    backend.db.sqlite.SessionLocal = original_session
    backend.api.strategies.SessionLocal = original_session
    backend.api.backtests.SessionLocal = original_session
    backend.db.SessionLocal = original_session


@pytest.fixture
def sample_strategy():
    """示例策略数据"""
    return {
        "name": "双均线策略",
        "description": "5日/20日均线交叉",
        "code": """
def initialize(context):
    context.short_period = 5
    context.long_period = 20

def handle_bar(context, bar):
    short_ma = context.history['close'].rolling(context.short_period).mean()
    long_ma = context.history['close'].rolling(context.long_period).mean()

    if short_ma.iloc[-1] > long_ma.iloc[-1]:
        return {'action': 'buy', 'quantity': 100}
    elif short_ma.iloc[-1] < long_ma.iloc[-1]:
        return {'action': 'sell', 'quantity': 100}
    return None
""".strip()
    }


@pytest.fixture
def sample_backtest_request():
    """示例回测请求数据"""
    return {
        "strategy_id": 1,
        "symbol": "600000.SH",
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "initial_capital": 1000000,
        "commission": 0.0003
    }


@pytest.fixture
def sample_kline_data():
    """示例 K线数据"""
    import pandas as pd
    from datetime import datetime, timedelta

    # 生成 100 天的模拟 K线数据
    dates = [datetime(2024, 1, 1) + timedelta(days=i) for i in range(100)]

    data = pd.DataFrame({
        'timestamp': dates,
        'open': [10.0 + i * 0.01 for i in range(100)],
        'high': [10.2 + i * 0.01 for i in range(100)],
        'low': [9.8 + i * 0.01 for i in range(100)],
        'close': [10.1 + i * 0.01 for i in range(100)],
        'volume': [1000000 + i * 1000 for i in range(100)],
        'amount': [10000000 + i * 10000 for i in range(100)]
    })

    return data

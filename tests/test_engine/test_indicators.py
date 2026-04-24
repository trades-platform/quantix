"""技术指标测试"""

import pandas as pd
import numpy as np
import pytest

from backend.engine.indicators import SymbolIndicators


@pytest.fixture
def price_data():
    """100 根 bar 的价格数据"""
    np.random.seed(42)
    n = 100
    dates = pd.date_range("2024-01-01", periods=n, freq="min")
    close = 10.0 + np.random.randn(n).cumsum() * 0.1
    high = close + np.abs(np.random.randn(n)) * 0.2
    low = close - np.abs(np.random.randn(n)) * 0.2
    open_ = close + np.random.randn(n) * 0.05
    return pd.DataFrame({
        "timestamp": dates,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": np.random.randint(10000, 100000, n).astype(float),
    })


def test_ma(price_data):
    """MA 计算"""
    ind = SymbolIndicators(price_data)
    ma5 = ind.ma(5)
    assert ma5 != 0.0
    # 验证值 = 最后 5 个 close 的均值
    expected = price_data["close"].tail(5).mean()
    assert abs(ma5 - expected) < 1e-10


def test_ma_insufficient_data(price_data):
    """数据不足时 MA 返回 0"""
    short_data = price_data.head(3)
    ind = SymbolIndicators(short_data)
    assert ind.ma(5) == 0.0


def test_ema(price_data):
    """EMA 计算"""
    ind = SymbolIndicators(price_data)
    ema12 = ind.ema(12)
    assert ema12 != 0.0


def test_ma_angle(price_data):
    """MA angle 返回 -90 到 90 之间的角度"""
    ind = SymbolIndicators(price_data)
    ind.set_current_idx(len(price_data))
    angle = ind.ma_angle(5)
    assert isinstance(angle, float)
    assert -90 < angle < 90


def test_macd(price_data):
    """MACD 返回三元组"""
    ind = SymbolIndicators(price_data)
    result = ind.macd()
    assert len(result) == 3
    macd_line, signal, hist = result
    assert isinstance(macd_line, float)


def test_rsi(price_data):
    """RSI 在 0-100 之间"""
    ind = SymbolIndicators(price_data)
    rsi = ind.rsi(14)
    assert 0 <= rsi <= 100


def test_rsi_insufficient_data():
    """RSI 数据不足返回 NaN"""
    short = pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=5, freq="min"),
        "open": [10.0] * 5,
        "high": [10.5] * 5,
        "low": [9.5] * 5,
        "close": [10.0, 10.1, 10.2, 10.3, 10.4],
        "volume": [1000.0] * 5,
    })
    ind = SymbolIndicators(short)
    import math
    assert math.isnan(ind.rsi(14))


def test_boll(price_data):
    """布林带返回 (upper, middle, lower) 三元组"""
    ind = SymbolIndicators(price_data)
    upper, middle, lower = ind.boll()
    assert upper > middle > lower


def test_atr(price_data):
    """ATR 为正数"""
    ind = SymbolIndicators(price_data)
    atr = ind.atr(14)
    assert atr > 0


def test_kdj(price_data):
    """KDJ 返回 (K, D, J) 三元组"""
    ind = SymbolIndicators(price_data)
    k, d, j = ind.kdj()
    assert isinstance(k, float)
    assert isinstance(d, float)
    assert isinstance(j, float)


def test_no_look_ahead_bias(price_data):
    """验证无前视偏差：只用尾部数据计算"""
    full_ind = SymbolIndicators(price_data)
    full_ma = full_ind.ma(10)

    # 只用最后 20 行数据
    partial_ind = SymbolIndicators(price_data.tail(20))
    partial_ma = partial_ind.ma(10)

    assert abs(full_ma - partial_ma) < 1e-10


def test_ma_period_1():
    """MA(1) 等于最新 close"""
    data = pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=5, freq="min"),
        "open": [10.0] * 5,
        "high": [10.5] * 5,
        "low": [9.5] * 5,
        "close": [10.0, 10.1, 10.2, 10.3, 10.4],
        "volume": [1000.0] * 5,
    })
    ind = SymbolIndicators(data)
    assert abs(ind.ma(1) - 10.4) < 1e-10

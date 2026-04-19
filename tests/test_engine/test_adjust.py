"""复权模块测试"""

import pandas as pd
import numpy as np
import pytest

from backend.engine.adjust import apply_factor


@pytest.fixture
def kline_data():
    """4 天的 K 线数据"""
    return pd.DataFrame({
        "timestamp": pd.date_range("2024-01-02", periods=4, freq="D"),
        "open": [10.0, 10.5, 11.0, 11.5],
        "high": [10.5, 11.0, 11.5, 12.0],
        "low": [9.5, 10.0, 10.5, 11.0],
        "close": [10.2, 10.8, 11.3, 11.8],
        "volume": [1000, 2000, 3000, 4000],
        "amount": [10000.0, 20000.0, 30000.0, 40000.0],
    })


@pytest.fixture
def factor_data():
    """复权因子（第 3 天除权，因子从 1.0 变为 1.5）"""
    return pd.DataFrame({
        "timestamp": pd.to_datetime(["2024-01-02", "2024-01-04"]),
        "factor": [1.0, 1.5],
    })


def test_apply_factor_none_mode(kline_data):
    """none 模式：直接返回原始价格"""
    result = apply_factor(kline_data, pd.DataFrame(), mode="none")
    assert "adjusted_open" in result.columns
    assert list(result["adjusted_open"]) == list(kline_data["open"])
    assert list(result["adjusted_close"]) == list(kline_data["close"])


def test_apply_factor_hfq(kline_data, factor_data):
    """后复权：adjusted = raw * factor"""
    result = apply_factor(kline_data, factor_data, mode="hfq")
    # Day 1-2: factor=1.0, Day 3-4: factor=1.5
    assert abs(result["adjusted_close"].iloc[0] - 10.2) < 1e-10  # 10.2 * 1.0
    assert abs(result["adjusted_close"].iloc[1] - 10.8) < 1e-10  # 10.8 * 1.0
    assert abs(result["adjusted_close"].iloc[2] - 11.3 * 1.5) < 1e-10  # 11.3 * 1.5
    assert abs(result["adjusted_close"].iloc[3] - 11.8 * 1.5) < 1e-10  # 11.8 * 1.5


def test_apply_factor_qfq(kline_data, factor_data):
    """前复权：adjusted = raw * factor / latest_factor，最新价不变"""
    result = apply_factor(kline_data, factor_data, mode="qfq")
    # latest_factor = 1.5
    # Day 1-2: factor=1.0, scale = 1.0/1.5 = 0.6667
    # Day 3-4: factor=1.5, scale = 1.5/1.5 = 1.0
    assert abs(result["adjusted_close"].iloc[2] - 11.3) < 1e-10  # 11.3 * 1.0
    assert abs(result["adjusted_close"].iloc[3] - 11.8) < 1e-10  # 11.8 * 1.0
    assert abs(result["adjusted_close"].iloc[0] - 10.2 * 1.0 / 1.5) < 1e-10


def test_apply_factor_empty_factor(kline_data):
    """空因子数据：返回原始价格"""
    empty_factor = pd.DataFrame(columns=["timestamp", "factor"])
    result = apply_factor(kline_data, empty_factor, mode="hfq")
    assert list(result["adjusted_close"]) == list(kline_data["close"])


def test_apply_factor_preserves_original(kline_data, factor_data):
    """复权不修改原始数据"""
    original_close = list(kline_data["close"])
    _ = apply_factor(kline_data, factor_data, mode="hfq")
    assert list(kline_data["close"]) == original_close


def test_apply_factor_invalid_mode(kline_data, factor_data):
    """无效模式应抛出异常"""
    with pytest.raises(ValueError, match="Invalid adjust mode"):
        apply_factor(kline_data, factor_data, mode="invalid")


def test_apply_factor_all_ohlc(kline_data, factor_data):
    """OHLC 四列都正确复权"""
    result = apply_factor(kline_data, factor_data, mode="hfq")
    # Day 3: factor=1.5
    idx = 2
    assert abs(result["adjusted_open"].iloc[idx] - kline_data["open"].iloc[idx] * 1.5) < 1e-10
    assert abs(result["adjusted_high"].iloc[idx] - kline_data["high"].iloc[idx] * 1.5) < 1e-10
    assert abs(result["adjusted_low"].iloc[idx] - kline_data["low"].iloc[idx] * 1.5) < 1e-10
    assert abs(result["adjusted_close"].iloc[idx] - kline_data["close"].iloc[idx] * 1.5) < 1e-10

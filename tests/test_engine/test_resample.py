"""K线重采样测试"""

import pandas as pd
import numpy as np
import pytest

from backend.engine.resample import resample_kline


@pytest.fixture
def minute_data():
    """生成 2 天的 1min K线数据（含两个交易时段）"""
    rows = []
    base = pd.Timestamp("2026-04-15")

    for day_offset in range(2):
        date = base + pd.Timedelta(days=day_offset)
        # 早盘 9:30-11:30 + 午盘 13:00-15:00
        for start_h, start_m in [(9, 30), (13, 0)]:
            for mins in range(121):  # 121 minutes per session
                h = start_h + (start_m + mins) // 60
                m = (start_m + mins) % 60
                t = date.replace(hour=h, minute=m)
                rows.append({
                    "timestamp": t,
                    "open": 10.0 + day_offset + mins * 0.001,
                    "high": 10.2 + day_offset + mins * 0.001,
                    "low": 9.8 + day_offset + mins * 0.001,
                    "close": 10.1 + day_offset + mins * 0.001,
                    "volume": 10000 + mins,
                    "amount": 100000.0 + mins * 10,
                })

    return pd.DataFrame(rows)


@pytest.fixture
def minute_data_with_midnight():
    """带有一根 00:00:00 日线汇总行的数据"""
    rows = [{
        "timestamp": pd.Timestamp("2026-04-15"),
        "open": 10.0,
        "high": 10.5,
        "low": 9.5,
        "close": 10.3,
        "volume": 5000000,
        "amount": 50000000.0,
    }]
    # 正常交易分钟线
    for mins in range(121):
        h = 9 + (30 + mins) // 60
        m = (30 + mins) % 60
        rows.append({
            "timestamp": pd.Timestamp("2026-04-15").replace(hour=h, minute=m),
            "open": 10.0 + mins * 0.001,
            "high": 10.2 + mins * 0.001,
            "low": 9.8 + mins * 0.001,
            "close": 10.1 + mins * 0.001,
            "volume": 10000 + mins,
            "amount": 100000.0 + mins * 10,
        })
    return pd.DataFrame(rows)


def test_resample_1min_passthrough(minute_data):
    """1min 应直接返回副本"""
    result = resample_kline(minute_data, "1min")
    assert len(result) == len(minute_data)
    assert result is not minute_data  # 是副本不是引用


def test_resample_5min(minute_data):
    """5min 重采样"""
    result = resample_kline(minute_data, "5min")
    assert len(result) > 0
    # 每根 5min bar 的起始时间应为有效交易时间
    for ts in result["timestamp"]:
        h, m = ts.hour, ts.minute
        tv = h * 100 + m
        assert (930 <= tv <= 1130) or (1300 <= tv <= 1500)


def test_resample_120min_sessions(minute_data):
    """120min 按 session 聚合，每天 2 根"""
    result = resample_kline(minute_data, "120min")
    # 2 天 x 2 session = 4 bars
    assert len(result) == 4
    # 时间戳应为 11:30 和 15:00
    times = result["timestamp"].dt.strftime("%H:%M").tolist()
    assert "11:30" in times
    assert "15:00" in times


def test_resample_120min_midnight_filtered(minute_data_with_midnight):
    """120min 应过滤掉 00:00:00 的日线汇总行"""
    result = resample_kline(minute_data_with_midnight, "120min")
    # 只有一天早盘数据 (没有午盘)，应该是 1 bar
    assert len(result) >= 1
    # 不应出现 00:00:00 的时间戳
    for ts in result["timestamp"]:
        assert ts.hour != 0 or ts.minute != 0


def test_resample_daily(minute_data):
    """日线聚合"""
    result = resample_kline(minute_data, "1D")
    assert len(result) == 2  # 2 天


def test_resample_daily_midnight_filtered(minute_data_with_midnight):
    """日线应过滤 00:00:00 行"""
    result = resample_kline(minute_data_with_midnight, "1D")
    assert len(result) == 1


def test_resample_daily_ohlc(minute_data):
    """日线 OHLC 聚合正确性"""
    result = resample_kline(minute_data, "1D")
    day1 = result.iloc[0]
    # open = 第一根 bar 的 open
    assert day1["open"] == minute_data.iloc[0]["open"]
    # close = 最后一根 bar 的 close
    day1_data = minute_data[minute_data["timestamp"].dt.date == minute_data.iloc[0]["timestamp"].date()]
    assert abs(day1["close"] - day1_data.iloc[-1]["close"]) < 1e-10


def test_resample_weekly():
    """周线聚合"""
    # 生成跨两周的数据
    dates = pd.date_range("2026-03-02 09:30", periods=20, freq="D")
    # 只保留工作日
    dates = dates[dates.dayofweek < 5]
    df = pd.DataFrame({
        "timestamp": dates,
        "open": range(len(dates)),
        "high": range(1, len(dates) + 1),
        "low": range(len(dates)),
        "close": range(1, len(dates) + 1),
        "volume": [1000] * len(dates),
        "amount": [10000.0] * len(dates),
    })
    result = resample_kline(df, "1W")
    assert len(result) >= 2


def test_resample_monthly():
    """月线聚合"""
    dates = pd.date_range("2026-01-05 09:30", periods=60, freq="D")
    dates = dates[dates.dayofweek < 5]
    df = pd.DataFrame({
        "timestamp": dates,
        "open": [10.0] * len(dates),
        "high": [11.0] * len(dates),
        "low": [9.0] * len(dates),
        "close": [10.5] * len(dates),
        "volume": [1000] * len(dates),
        "amount": [10000.0] * len(dates),
    })
    result = resample_kline(df, "1M")
    assert len(result) >= 2


def test_resample_quarterly():
    """季线聚合"""
    dates = pd.date_range("2025-01-02 09:30", periods=250, freq="D")
    dates = dates[dates.dayofweek < 5]
    df = pd.DataFrame({
        "timestamp": dates,
        "open": [10.0] * len(dates),
        "high": [11.0] * len(dates),
        "low": [9.0] * len(dates),
        "close": [10.5] * len(dates),
        "volume": [1000] * len(dates),
        "amount": [10000.0] * len(dates),
    })
    result = resample_kline(df, "1Q")
    assert len(result) >= 3


def test_resample_empty():
    """空数据直接返回"""
    empty = pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume", "amount"])
    result = resample_kline(empty, "5min")
    assert len(result) == 0

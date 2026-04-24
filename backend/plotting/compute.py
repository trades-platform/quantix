"""指标序列计算 — 向量化实现，与 SymbolIndicators 公式一致"""

from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd

from backend.plotting.types import (
    BandSeries,
    IndicatorSeries,
    MAIN,
    ScalarSeries,
    SeriesKind,
    VOLUME,
)


def _mask_before_period(series: pd.Series, period: int) -> pd.Series:
    """匹配 SymbolIndicators 行为：数据不足 period 时无有效值"""
    result = series.copy()
    result.iloc[:period] = np.nan
    return result


def compute_ma(df: pd.DataFrame, period: int = 5, name: str | None = None,
               pane: str = MAIN, color: str | None = None) -> IndicatorSeries:
    # SymbolIndicators: data["close"].tail(period).mean()
    raw = df["close"].rolling(period, min_periods=period).mean()
    data = _mask_before_period(raw, period).tolist()
    return IndicatorSeries(
        name=name or f"MA({period})", pane=pane, kind=SeriesKind.LINE,
        data=ScalarSeries(data=data), color=color,
    )


def compute_ema(df: pd.DataFrame, period: int = 20, name: str | None = None,
                pane: str = MAIN, color: str | None = None) -> IndicatorSeries:
    # SymbolIndicators: data["close"].ewm(span=period, adjust=False).mean()
    raw = df["close"].ewm(span=period, adjust=False).mean()
    data = _mask_before_period(raw, period).tolist()
    return IndicatorSeries(
        name=name or f"EMA({period})", pane=pane, kind=SeriesKind.LINE,
        data=ScalarSeries(data=data), color=color,
    )


def compute_boll(df: pd.DataFrame, period: int = 20, std_dev: float = 2.0,
                 name: str | None = None, pane: str = MAIN,
                 color: str | None = None) -> IndicatorSeries:
    # SymbolIndicators: close_tail = data["close"].tail(period), mean + std_dev * std
    rolling = df["close"].rolling(period, min_periods=period)
    middle = rolling.mean()
    std = rolling.std(ddof=0)
    upper = middle + std_dev * std
    lower = middle - std_dev * std
    # NaN for insufficient data
    middle = middle.fillna(np.nan)
    upper = upper.fillna(np.nan)
    lower = lower.fillna(np.nan)
    return IndicatorSeries(
        name=name or f"BOLL({period},{std_dev})", pane=pane, kind=SeriesKind.BAND,
        data=BandSeries(upper=upper.tolist(), middle=middle.tolist(), lower=lower.tolist()),
        color=color or "#2196F3",
    )


def compute_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9,
                 name: str | None = None, pane: str = "macd",
                 color: str | None = None) -> IndicatorSeries:
    # SymbolIndicators: ewm(span=fast, adjust=False) - ewm(span=slow, adjust=False)
    close = df["close"]
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal, adjust=False).mean()
    hist = dif - dea
    return IndicatorSeries(
        name=name or f"MACD({fast},{slow},{signal})", pane=pane, kind=SeriesKind.BAND,
        data=BandSeries(extra={"dif": dif.tolist(), "dea": dea.tolist(), "histogram": hist.tolist()}),
        color=color,
    )


def compute_rsi(df: pd.DataFrame, period: int = 14, name: str | None = None,
                pane: str = "rsi", color: str | None = None) -> IndicatorSeries:
    # SymbolIndicators: gain.tail(period).mean() / loss.tail(period).mean() (SMA RSI)
    close = df["close"]
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    # Match the SMA-based RSI from SymbolIndicators (not Wilder EMA smoothing)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    # Before we have `period` data points, SymbolIndicators returns NaN
    rsi.iloc[:period] = np.nan

    return IndicatorSeries(
        name=name or f"RSI({period})", pane=pane, kind=SeriesKind.LINE,
        data=ScalarSeries(data=rsi.tolist()), color=color or "#FF9800",
    )


def compute_kdj(df: pd.DataFrame, n: int = 9, m1: int = 3, m2: int = 3,
                name: str | None = None, pane: str = "kdj",
                color: str | None = None) -> IndicatorSeries:
    # Match SymbolIndicators KDJ: cumulative smoothing from 50.0
    k_vals, d_vals, j_vals = [np.nan] * len(df), [np.nan] * len(df), [np.nan] * len(df)
    k, d = 50.0, 50.0
    alpha_k = 1.0 / m1
    alpha_d = 1.0 / m2

    for i in range(n - 1, len(df)):
        window = df.iloc[max(0, i - n + 1):i + 1]
        highest = window["high"].max()
        lowest = window["low"].min()
        rsv = 50.0 if highest == lowest else 100.0 * (window["close"].iloc[-1] - lowest) / (highest - lowest)
        k = (1 - alpha_k) * k + alpha_k * rsv
        d = (1 - alpha_d) * d + alpha_d * k
        k_vals[i] = k
        d_vals[i] = d
        j_vals[i] = 3 * k - 2 * d

    return IndicatorSeries(
        name=name or f"KDJ({n},{m1},{m2})", pane=pane, kind=SeriesKind.BAND,
        data=BandSeries(extra={"k": k_vals, "d": d_vals, "j": j_vals}),
        color=color,
    )


def compute_atr(df: pd.DataFrame, period: int = 14, name: str | None = None,
                pane: str = "atr", color: str | None = None) -> IndicatorSeries:
    # SymbolIndicators: tr = max(H-L, |H-prevC|, |L-prevC|), then tail(period).mean()
    high = df["high"]
    low = df["low"]
    prev_close = df["close"].shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(period, min_periods=period).mean()
    return IndicatorSeries(
        name=name or f"ATR({period})", pane=pane, kind=SeriesKind.LINE,
        data=ScalarSeries(data=atr.fillna(np.nan).tolist()), color=color or "#AB47BC",
    )


def compute_volume(df: pd.DataFrame, name: str | None = None,
                   pane: str = VOLUME, color: str | None = None) -> IndicatorSeries:
    return IndicatorSeries(
        name=name or "Volume", pane=pane, kind=SeriesKind.HISTOGRAM,
        data=ScalarSeries(data=df["volume"].astype(float).tolist()),
        color=color or "#616161",
    )


def compute_equity_curve(equity_curve: list[float], n_bars: int | None = None) -> IndicatorSeries:
    data = list(equity_curve)
    if not data:
        return IndicatorSeries(
            name="Equity", pane="equity", kind=SeriesKind.LINE,
            data=ScalarSeries(data=[]), color="#26a69a",
        )
    if n_bars is not None:
        if len(data) < n_bars:
            data = data + [data[-1]] * (n_bars - len(data))
        else:
            data = data[:n_bars]
    return IndicatorSeries(
        name="Equity", pane="equity", kind=SeriesKind.LINE,
        data=ScalarSeries(data=data), color="#26a69a",
    )


def compute_drawdown(equity_curve: list[float], n_bars: int | None = None) -> IndicatorSeries:
    data = list(equity_curve)
    if not data:
        return IndicatorSeries(
            name="Drawdown", pane="drawdown", kind=SeriesKind.HISTOGRAM,
            data=ScalarSeries(data=[]), color="#ef5350",
        )
    if n_bars is not None:
        if len(data) < n_bars:
            data = data + [data[-1]] * (n_bars - len(data))
        else:
            data = data[:n_bars]
    equity = np.array(data, dtype=float)
    peak = np.maximum.accumulate(equity)
    with np.errstate(divide="ignore", invalid="ignore"):
        dd = np.where(peak != 0, (equity - peak) / peak, 0.0)
    return IndicatorSeries(
        name="Drawdown", pane="drawdown", kind=SeriesKind.HISTOGRAM,
        data=ScalarSeries(data=dd.tolist()), color="#ef5350",
    )


# --- Registry ---

INDICATOR_REGISTRY: dict[str, Callable] = {
    "ma": compute_ma,
    "ema": compute_ema,
    "boll": compute_boll,
    "macd": compute_macd,
    "rsi": compute_rsi,
    "kdj": compute_kdj,
    "atr": compute_atr,
    "volume": compute_volume,
}


def compute_indicator(df: pd.DataFrame, kind: str, params: dict) -> IndicatorSeries:
    fn = INDICATOR_REGISTRY.get(kind)
    if fn is None:
        raise ValueError(f"Unknown indicator: {kind!r}. Available: {list(INDICATOR_REGISTRY)}")
    return fn(df, **params)

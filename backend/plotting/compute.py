"""指标序列计算 — 向量化实现，公式统一来自 core-ti（见 backend.engine.ti）

与回测引擎的 SymbolIndicators 共用同一个 core-ti 引擎，保证图表与
回测指标口径完全一致。
"""

from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd

from backend.engine import ti
from backend.plotting.types import (
    BandSeries,
    IndicatorSeries,
    MAIN,
    ScalarSeries,
    SeriesKind,
    VOLUME,
)


def compute_ma(df: pd.DataFrame, period: int = 5, name: str | None = None,
               pane: str = MAIN, color: str | None = None) -> IndicatorSeries:
    col = ti.compute(df, "sma", {"period": period}).iloc[:, 0]
    return IndicatorSeries(
        name=name or f"MA({period})", pane=pane, kind=SeriesKind.LINE,
        data=ScalarSeries(data=col.tolist()), color=color,
    )


def compute_ema(df: pd.DataFrame, period: int = 20, name: str | None = None,
                pane: str = MAIN, color: str | None = None) -> IndicatorSeries:
    col = ti.compute(df, "ema", {"period": period}).iloc[:, 0]
    return IndicatorSeries(
        name=name or f"EMA({period})", pane=pane, kind=SeriesKind.LINE,
        data=ScalarSeries(data=col.tolist()), color=color,
    )


def compute_boll(df: pd.DataFrame, period: int = 20, std_dev: float = 2.0,
                 name: str | None = None, pane: str = MAIN,
                 color: str | None = None) -> IndicatorSeries:
    bands = ti.compute(df, "bb", {"period": period, "std": std_dev})
    upper, middle, lower = bands.iloc[:, 0], bands.iloc[:, 1], bands.iloc[:, 2]
    return IndicatorSeries(
        name=name or f"BOLL({period},{std_dev})", pane=pane, kind=SeriesKind.BAND,
        data=BandSeries(upper=upper.tolist(), middle=middle.tolist(), lower=lower.tolist()),
        color=color or "#2196F3",
    )


def compute_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9,
                 name: str | None = None, pane: str = "macd",
                 color: str | None = None) -> IndicatorSeries:
    macd = ti.compute(df, "macd", {"fast": fast, "slow": slow, "signal": signal})
    dif, dea, hist = macd.iloc[:, 0], macd.iloc[:, 1], macd.iloc[:, 2]
    return IndicatorSeries(
        name=name or f"MACD({fast},{slow},{signal})", pane=pane, kind=SeriesKind.BAND,
        data=BandSeries(extra={"dif": dif.tolist(), "dea": dea.tolist(), "histogram": hist.tolist()}),
        color=color,
    )


def compute_rsi(df: pd.DataFrame, period: int = 14, name: str | None = None,
                pane: str = "rsi", color: str | None = None) -> IndicatorSeries:
    col = ti.compute(df, "rsi", {"period": period}).iloc[:, 0]
    return IndicatorSeries(
        name=name or f"RSI({period})", pane=pane, kind=SeriesKind.LINE,
        data=ScalarSeries(data=col.tolist()), color=color or "#FF9800",
    )


def compute_atr(df: pd.DataFrame, period: int = 14, name: str | None = None,
                pane: str = "atr", color: str | None = None) -> IndicatorSeries:
    col = ti.compute(df, "atr", {"period": period}).iloc[:, 0]
    return IndicatorSeries(
        name=name or f"ATR({period})", pane=pane, kind=SeriesKind.LINE,
        data=ScalarSeries(data=col.tolist()), color=color or "#AB47BC",
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
    "atr": compute_atr,
    "volume": compute_volume,
}


def compute_indicator(df: pd.DataFrame, kind: str, params: dict) -> IndicatorSeries:
    fn = INDICATOR_REGISTRY.get(kind)
    if fn is None:
        raise ValueError(f"Unknown indicator: {kind!r}. Available: {list(INDICATOR_REGISTRY)}")
    return fn(df, **params)


# --- Batch pre-computation -------------------------------------------------

# 每种图层对应的 core-ti 指标规格（仅作性能预热用；正确性不依赖此表：
# 即便参数与实际调用略有出入，也只是少一次预热、compute_indicator 会自行补算）。
_PREWARM_SPECS: dict[str, Callable[[dict], tuple[str, dict]]] = {
    "ma": lambda p: ("sma", {"period": p.get("period", 5)}),
    "ema": lambda p: ("ema", {"period": p.get("period", 20)}),
    "boll": lambda p: ("bb", {"period": p.get("period", 20), "std": p.get("std_dev", 2.0)}),
    "macd": lambda p: ("macd", {"fast": p.get("fast", 12), "slow": p.get("slow", 26), "signal": p.get("signal", 9)}),
    "rsi": lambda p: ("rsi", {"period": p.get("period", 14)}),
    "atr": lambda p: ("atr", {"period": p.get("period", 14)}),
}


def enrich_for_layers(df: pd.DataFrame, layers) -> pd.DataFrame:
    """为一组图层一次性预计算全部 core-ti 指标列，返回带列的 df 副本。

    对返回值再调用 :func:`compute_indicator` 时会直接复用已算好的列，避免逐个
    指标重复拷贝数据。*layers* 中的每项需带 ``indicator`` 与 ``params`` 属性。
    """
    specs: list[tuple[str, dict]] = []
    for spec in layers:
        factory = _PREWARM_SPECS.get(spec.indicator)
        if factory is not None:
            specs.append(factory(spec.params))
    return ti.compute_many(df, specs)


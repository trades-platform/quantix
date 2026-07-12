"""技术指标计算模块

所有指标公式统一来自 core-ti（见 :mod:`backend.engine.ti`），本模块只负责
把「逐 bar 标量」的回测访问方式适配到 core-ti 的向量化计算：在完整历史上按
需计算并缓存整列指标，再按当前可见截止位置读取标量值。

由于所有指标均为因果指标（第 t 根的值只依赖 ≤ t 的数据），在完整序列上计算
后读取 ``current_idx - 1`` 位置的值，与只用 ``data[:current_idx]`` 计算的结果
完全一致，因此不会引入前视偏差。
"""

import math

import pandas as pd

from backend.engine import ti


class SymbolIndicators:
    """单个标的的技术指标计算器

    使用 set_current_idx() 增量更新可见数据范围。指标整列由 core-ti 计算并
    缓存到工作副本，逐 bar 访问只做一次数组取值，无需重复计算。
    """

    def __init__(self, data: pd.DataFrame):
        """初始化指标计算器

        Args:
            data: 完整历史K线数据，包含列: timestamp, open, high, low, close, volume
        """
        # 独立工作副本，用于原地累加 core-ti 计算出的指标列
        self._work = data.reset_index(drop=True).copy()
        self._current_idx = len(self._work)

    def set_current_idx(self, idx: int):
        """设置当前可见数据的截止行索引（不含 idx）"""
        self._current_idx = idx

    def _value(self, col: str) -> float:
        """读取指标列在当前可见截止位置（current_idx - 1）的标量值"""
        i = self._current_idx - 1
        if i < 0 or i >= len(self._work):
            return float("nan")
        return float(self._work[col].iloc[i])

    def ma(self, period: int) -> float:
        """简单移动平均线

        Args:
            period: 周期

        Returns:
            MA 值，数据不足时返回 0.0
        """
        if self._current_idx < period:
            return 0.0
        (col,) = ti.ensure_columns(self._work, "sma", {"period": period})
        val = self._value(col)
        return 0.0 if math.isnan(val) else val

    def ema(self, period: int) -> float:
        """指数移动平均线

        Args:
            period: 周期

        Returns:
            EMA 值，数据不足时返回 0.0
        """
        if self._current_idx < period:
            return 0.0
        (col,) = ti.ensure_columns(self._work, "ema", {"period": period})
        val = self._value(col)
        return 0.0 if math.isnan(val) else val

    def macd(self, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[float, float, float]:
        """MACD 指标

        Args:
            fast: 快线周期
            slow: 慢线周期
            signal: 信号线周期

        Returns:
            (macd_line, signal_line, histogram)
        """
        if self._current_idx < slow + signal:
            return (0.0, 0.0, 0.0)
        line_col, signal_col, hist_col = ti.ensure_columns(
            self._work, "macd", {"fast": fast, "slow": slow, "signal": signal}
        )
        return (self._value(line_col), self._value(signal_col), self._value(hist_col))

    def rsi(self, period: int = 14) -> float:
        """相对强弱指标（Wilder 平滑）

        Args:
            period: 周期

        Returns:
            RSI 值 (0-100)，数据不足时返回 NaN
        """
        if self._current_idx < period:
            return float("nan")
        (col,) = ti.ensure_columns(self._work, "rsi", {"period": period})
        return self._value(col)

    def boll(self, period: int = 20, std_dev: float = 2.0) -> tuple[float, float, float]:
        """布林带

        Args:
            period: 周期
            std_dev: 标准差倍数

        Returns:
            (upper, middle, lower)
        """
        if self._current_idx < period:
            return (float("nan"), float("nan"), float("nan"))
        upper_col, mid_col, lower_col = ti.ensure_columns(
            self._work, "bb", {"period": period, "std": std_dev}
        )
        return (self._value(upper_col), self._value(mid_col), self._value(lower_col))

    def atr(self, period: int = 14) -> float:
        """平均真实波幅（Wilder 平滑）

        Args:
            period: 周期

        Returns:
            ATR 值，数据不足时返回 NaN
        """
        if self._current_idx < period + 1:
            return float("nan")
        (col,) = ti.ensure_columns(self._work, "atr", {"period": period})
        return self._value(col)

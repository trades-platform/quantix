"""技术指标计算模块"""

import pandas as pd
import numpy as np


class SymbolIndicators:
    """单个标的的技术指标计算器"""

    def __init__(self, data: pd.DataFrame):
        """初始化指标计算器

        Args:
            data: 历史K线数据，包含列: timestamp, open, high, low, close, volume
        """
        self._data = data

    def ma(self, period: int) -> float:
        """简单移动平均线

        Args:
            period: 周期

        Returns:
            MA 值，数据不足时返回 0.0
        """
        if len(self._data) < period:
            return 0.0
        return float(self._data["close"].tail(period).mean())

    def ema(self, period: int) -> float:
        """指数移动平均线

        Args:
            period: 周期

        Returns:
            EMA 值，数据不足时返回 0.0
        """
        if len(self._data) < period:
            return 0.0
        return float(self._data["close"].ewm(span=period, adjust=False).mean().iloc[-1])

    def macd(self, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[float, float, float]:
        """MACD 指标

        Args:
            fast: 快线周期
            slow: 慢线周期
            signal: 信号线周期

        Returns:
            (macd_line, signal_line, histogram)
        """
        if len(self._data) < slow + signal:
            return (0.0, 0.0, 0.0)

        close = self._data["close"]
        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line

        return (
            float(macd_line.iloc[-1]),
            float(signal_line.iloc[-1]),
            float(histogram.iloc[-1]),
        )

    def rsi(self, period: int = 14) -> float:
        """相对强弱指标

        Args:
            period: 周期

        Returns:
            RSI 值 (0-100)，数据不足时返回 NaN
        """
        if len(self._data) < period * 2:
            return np.nan

        close = self._data["close"].tail(period * 2)
        delta = close.diff()

        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)

        avg_gain = gain.tail(period).mean()
        avg_loss = loss.tail(period).mean()

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return float(rsi)

    def boll(self, period: int = 20, std_dev: float = 2.0) -> tuple[float, float, float]:
        """布林带

        Args:
            period: 周期
            std_dev: 标准差倍数

        Returns:
            (upper, middle, lower)
        """
        if len(self._data) < period:
            return (np.nan, np.nan, np.nan)

        close_tail = self._data["close"].tail(period)
        middle = float(close_tail.mean())
        std = float(close_tail.std())
        upper = middle + std_dev * std
        lower = middle - std_dev * std

        return (upper, middle, lower)

    def atr(self, period: int = 14) -> float:
        """平均真实波幅

        Args:
            period: 周期

        Returns:
            ATR 值，数据不足时返回 NaN
        """
        if len(self._data) < period + 1:
            return np.nan

        high = self._data["high"]
        low = self._data["low"]
        close = self._data["close"]

        prev_close = close.shift(1)

        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        atr = tr.tail(period).mean()

        return float(atr)

    def kdj(self, n: int = 9, m1: int = 3, m2: int = 3) -> tuple[float, float, float]:
        """随机指标 (KDJ)

        Args:
            n: RSV 周期
            m1: K 值平滑周期
            m2: D 值平滑周期

        Returns:
            (K, D, J)
        """
        if len(self._data) < n + m1 + m2:
            return (np.nan, np.nan, np.nan)

        # 需要足够的历史数据来累积 K/D
        lookback = n + m1 + m2
        data = self._data.tail(lookback)

        k = 50.0
        d = 50.0

        alpha_k = 1.0 / m1
        alpha_d = 1.0 / m2

        for i in range(n - 1, len(data)):
            window = data.iloc[max(0, i - n + 1):i + 1]
            highest = window["high"].max()
            lowest = window["low"].min()

            if highest == lowest:
                rsv = 50.0
            else:
                rsv = 100.0 * (data["close"].iloc[i] - lowest) / (highest - lowest)

            k = (1 - alpha_k) * k + alpha_k * rsv
            d = (1 - alpha_d) * d + alpha_d * k

        j = 3 * k - 2 * d

        return (float(k), float(d), float(j))

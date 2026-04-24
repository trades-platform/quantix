"""技术指标计算模块"""

import pandas as pd
import numpy as np


class SymbolIndicators:
    """单个标的的技术指标计算器

    使用 set_current_idx() 增量更新可见数据范围，
    避免每根 bar 重建对象和全量重算。
    """

    def __init__(self, data: pd.DataFrame):
        """初始化指标计算器

        Args:
            data: 完整历史K线数据，包含列: timestamp, open, high, low, close, volume
        """
        self._data = data
        self._current_idx = 0

    def set_current_idx(self, idx: int):
        """设置当前可见数据的截止行索引（不含 idx）"""
        self._current_idx = idx

    @property
    def _visible(self) -> pd.DataFrame:
        """当前可见的数据切片"""
        return self._data.iloc[:self._current_idx]

    def ma(self, period: int) -> float:
        """简单移动平均线

        Args:
            period: 周期

        Returns:
            MA 值，数据不足时返回 0.0
        """
        data = self._visible
        if len(data) < period:
            return 0.0
        return float(data["close"].tail(period).mean())

    def ema(self, period: int) -> float:
        """指数移动平均线

        Args:
            period: 周期

        Returns:
            EMA 值，数据不足时返回 0.0
        """
        data = self._visible
        if len(data) < period:
            return 0.0
        return float(data["close"].ewm(span=period, adjust=False).mean().iloc[-1])

    def ma_angle(self, period: int, lookback: int = 1, scale: float = 100.0) -> float:
        """均线角度

        基于均线在 lookback 个 bar 内的相对变化率，通过 arctan 压缩到 -90~90 度。
        scale 越大，对同样涨跌幅给出的角度越大。
        """
        data = self._visible
        required = period + lookback
        if len(data) < required:
            return 0.0

        ma_series = data["close"].rolling(window=period).mean()
        current_ma = float(ma_series.iloc[-1])
        prev_ma = float(ma_series.iloc[-(lookback + 1)])
        if prev_ma == 0:
            return 0.0

        slope = ((current_ma - prev_ma) / prev_ma) / lookback
        return float(np.degrees(np.arctan(slope * scale)))

    def macd(self, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[float, float, float]:
        """MACD 指标

        Args:
            fast: 快线周期
            slow: 慢线周期
            signal: 信号线周期

        Returns:
            (macd_line, signal_line, histogram)
        """
        data = self._visible
        if len(data) < slow + signal:
            return (0.0, 0.0, 0.0)

        close = data["close"]
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
        data = self._visible
        if len(data) < period * 2:
            return np.nan

        close = data["close"].tail(period * 2)
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
        data = self._visible
        if len(data) < period:
            return (np.nan, np.nan, np.nan)

        close_tail = data["close"].tail(period)
        middle = float(close_tail.mean())
        std = float(close_tail.std(ddof=0))
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
        data = self._visible
        if len(data) < period + 1:
            return np.nan

        high = data["high"]
        low = data["low"]
        close = data["close"]

        prev_close = close.shift(1)

        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        atr = tr.tail(period).mean()

        return float(atr)

    def roc(self, period: int) -> float:
        """变动率指标 (Rate of Change / Momentum)

        Args:
            period: 周期

        Returns:
            ROC 值 (当前价相对 N 周期前收盘价的变化率)，数据不足时返回 0.0
        """
        data = self._visible
        if len(data) < period + 1:
            return 0.0

        prev_close = float(data["close"].iloc[-(period + 1)])
        current_close = float(data["close"].iloc[-1])
        if prev_close == 0:
            return 0.0

        return (current_close - prev_close) / prev_close

    def std(self, period: int) -> float:
        """收盘价标准差

        Args:
            period: 周期

        Returns:
            标准差，数据不足时返回 0.0
        """
        data = self._visible
        if len(data) < period:
            return 0.0
        return float(data["close"].tail(period).std(ddof=0))

    def history(self, field: str, period: int) -> list[float]:
        """获取最近 N 个字段值

        Args:
            field: 字段名，如 "close", "high", "low", "volume"
            period: 周期

        Returns:
            最近 N 个值的列表，数据不足时返回全部可用值
        """
        data = self._visible
        if len(data) == 0:
            return []
        return data[field].tail(period).tolist()

    def kdj(self, n: int = 9, m1: int = 3, m2: int = 3) -> tuple[float, float, float]:
        """随机指标 (KDJ)

        Args:
            n: RSV 周期
            m1: K 值平滑周期
            m2: D 值平滑周期

        Returns:
            (K, D, J)
        """
        data = self._visible
        if len(data) < n + m1 + m2:
            return (np.nan, np.nan, np.nan)

        # 需要足够的历史数据来累积 K/D
        lookback = n + m1 + m2
        visible_tail = data.tail(lookback)

        k = 50.0
        d = 50.0

        alpha_k = 1.0 / m1
        alpha_d = 1.0 / m2

        for i in range(n - 1, len(visible_tail)):
            window = visible_tail.iloc[max(0, i - n + 1):i + 1]
            highest = window["high"].max()
            lowest = window["low"].min()

            if highest == lowest:
                rsv = 50.0
            else:
                rsv = 100.0 * (visible_tail["close"].iloc[i] - lowest) / (highest - lowest)

            k = (1 - alpha_k) * k + alpha_k * rsv
            d = (1 - alpha_d) * d + alpha_d * k

        j = 3 * k - 2 * d

        return (float(k), float(d), float(j))

"""K线重采样模块"""

import pandas as pd


# 支持的周期映射到 pandas offset alias（分钟级）
PERIOD_MAP = {
    "1min": "1min",
    "5min": "5min",
    "15min": "15min",
    "30min": "30min",
    "60min": "1h",
    "120min": "120min",  # special: session-based
}

# 所有支持的有效周期
VALID_PERIODS = (
    "1min", "5min", "15min", "30min", "60min", "120min",
    "1D", "1W", "1M", "1Q",
)


def _agg_ohlcva(df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    """按指定列分组做 OHLCV+amount 聚合。"""
    result = df.groupby(group_col).agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
        "amount": "sum",
        "timestamp": "first",
    }).reset_index(drop=True)
    result = result.sort_values("timestamp").reset_index(drop=True)
    cols = ["timestamp", "open", "high", "low", "close", "volume", "amount"]
    return result[cols]


def _resample_by_session(df: pd.DataFrame) -> pd.DataFrame:
    """按 A 股交易时段聚合为 120min K 线。

    早盘 9:30-11:30 和午盘 13:00-15:00 各产生一根 K 线。
    """
    df = df.copy()
    # 过滤掉非交易时间的行（如日线汇总数据 00:00:00）
    hour = df["timestamp"].dt.hour
    minute = df["timestamp"].dt.minute
    time_val = hour * 100 + minute
    df = df[(time_val >= 930) | ((time_val >= 1300) & (time_val <= 1500))]

    df["date"] = df["timestamp"].dt.date
    df["session"] = hour * 100 + df["timestamp"].dt.minute  # HHMM int

    # 标记早盘 (< 12:00) 和午盘 (>= 12:00)
    df["session_id"] = df["session"].apply(
        lambda t: "morning" if t < 1200 else "afternoon"
    )

    result = (
        df.groupby(["date", "session_id"], sort=False)
        .agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
            "amount": "sum",
            "timestamp": "last",
        })
        .reset_index(drop=True)
    )

    # Ensure chronological order
    result = result.sort_values("timestamp").reset_index(drop=True)

    # 保留列顺序，去掉临时列
    cols = ["timestamp", "open", "high", "low", "close", "volume", "amount"]
    return result[cols]


def _resample_daily(df: pd.DataFrame) -> pd.DataFrame:
    """日线聚合。过滤非交易时间行后按日期分组。"""
    df = df.copy()
    # 过滤掉非交易时间的行（如日线汇总数据 00:00:00）
    time_val = df["timestamp"].dt.hour * 100 + df["timestamp"].dt.minute
    df = df[(time_val >= 930) | ((time_val >= 1300) & (time_val <= 1500))]

    df["date"] = df["timestamp"].dt.date
    result = df.groupby("date").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
        "amount": "sum",
        "timestamp": "first",
    }).reset_index(drop=True)
    return result.sort_values("timestamp").reset_index(drop=True)[
        ["timestamp", "open", "high", "low", "close", "volume", "amount"]
    ]


def _resample_weekly(df: pd.DataFrame) -> pd.DataFrame:
    """周线聚合。基于交易日数据，按自然周分组。

    使用每个交易日的 isocalendar week 作为分组键，
    天然跳过非交易日的间隙。
    """
    daily = _resample_daily(df)
    # isocalendar().week 返回 ISO 周编号，配合年份可唯一定位一周
    iso = daily["timestamp"].dt.isocalendar()
    daily["_week_key"] = daily["timestamp"].dt.strftime("%Y-W%V")
    return _agg_ohlcva(daily, "_week_key")


def _resample_monthly(df: pd.DataFrame) -> pd.DataFrame:
    """月线聚合。基于交易日数据，按年-月分组。"""
    daily = _resample_daily(df)
    daily["_month_key"] = daily["timestamp"].dt.strftime("%Y-%m")
    return _agg_ohlcva(daily, "_month_key")


def _resample_quarterly(df: pd.DataFrame) -> pd.DataFrame:
    """季线聚合。基于交易日数据，按年-季分组。"""
    daily = _resample_daily(df)
    daily["_quarter_key"] = daily["timestamp"].dt.strftime("%Y-Q") + (
        daily["timestamp"].dt.quarter.astype(str)
    )
    return _agg_ohlcva(daily, "_quarter_key")


def resample_kline(kline_df: pd.DataFrame, period: str) -> pd.DataFrame:
    """重采样K线数据到不同周期

    Args:
        kline_df: K线数据，包含列: timestamp, open, high, low, close, volume, amount
        period: 目标周期，支持 "1min", "5min", "15min", "30min", "60min", "120min",
                "1D", "1W", "1M", "1Q"

    Returns:
        重采样后的K线数据
    """
    if len(kline_df) == 0:
        return kline_df.copy()

    # 如果是 1min，直接返回
    if period == "1min":
        return kline_df.copy()

    # 确保 timestamp 是 datetime 类型
    df = kline_df.copy()
    if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
        df['timestamp'] = pd.to_datetime(df['timestamp'])

    df = df.sort_values('timestamp').reset_index(drop=True)

    if period == "1D":
        result = _resample_daily(df)

    elif period == "1W":
        result = _resample_weekly(df)

    elif period == "1M":
        result = _resample_monthly(df)

    elif period == "1Q":
        result = _resample_quarterly(df)

    elif period == "120min":
        result = _resample_by_session(df)

    else:
        # 分钟线重采样（5min, 15min, 30min, 60min）
        df_indexed = df.set_index('timestamp')

        offset = PERIOD_MAP[period]
        resampled = df_indexed.resample(
            rule=offset,
            closed='left',
            label='left'
        ).agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum',
            'amount': 'sum',
        })

        resampled = resampled.reset_index()

        # A股交易时段过滤
        resampled['time_value'] = (
            resampled['timestamp'].dt.hour * 100
            + resampled['timestamp'].dt.minute
        )

        def is_valid_trading_time(ts):
            time_val = ts.hour * 100 + ts.minute

            if period == "5min":
                valid_starts = []
                for t in range(930, 1131, 5):
                    valid_starts.append(t)
                for t in range(1300, 1501, 5):
                    valid_starts.append(t)
                return time_val in valid_starts
            elif period == "15min":
                valid_starts = [930, 945, 1000, 1015, 1030, 1045, 1100, 1115,
                               1300, 1315, 1330, 1345, 1400, 1415, 1430, 1445]
                return time_val in valid_starts
            elif period == "30min":
                valid_starts = [930, 1000, 1030, 1100, 1300, 1330, 1400, 1430]
                return time_val in valid_starts
            elif period == "60min":
                valid_starts = [930, 1030, 1100, 1300, 1400]
                return time_val in valid_starts

            in_morning = 930 <= time_val <= 1130
            in_afternoon = 1300 <= time_val <= 1500
            return in_morning or in_afternoon

        resampled = resampled[resampled['timestamp'].apply(is_valid_trading_time)]
        resampled = resampled.drop(columns=['time_value'])
        resampled = resampled.dropna()
        result = resampled.reset_index(drop=True)

    return result

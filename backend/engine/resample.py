"""K线重采样模块"""

import numpy as np
import pandas as pd


# 支持的周期映射到 pandas offset alias（分钟级）
PERIOD_MAP = {
    "1min": "1min",
    "5min": "5min",
    "15min": "15min",
    "30min": "30min",
    "120min": "120min",  # special: session-based
}

# 所有支持的有效周期
VALID_PERIODS = (
    "1min", "5min", "15min", "30min", "60min", "120min",
    "1D", "1W", "1M", "1Q",
)

# 标准K线列（顺序）
_KLINE_COLS = ["timestamp", "open", "high", "low", "close", "volume", "amount"]


def _in_trading_hours(ts: pd.Series) -> pd.Series:
    """判断时间序列是否落在 A 股交易时段内"""
    tv = ts.dt.hour * 100 + ts.dt.minute
    return ((tv >= 930) & (tv <= 1130)) | ((tv >= 1300) & (tv <= 1500))


def _is_daily_data(ts: pd.Series) -> bool:
    """判断数据是否已经是日线格式（所有时间戳时间部分相同）"""
    return len(ts.dt.time.unique()) <= 1


def _resample_60min(df: pd.DataFrame) -> pd.DataFrame:
    """按 A 股交易时段聚合为 60min K 线。

    A 股每天交易 4 小时，产生 4 根 60min bar：
      早盘：9:30-10:29, 10:30-11:30
      午盘：13:00-13:59, 14:00-15:00
    时间戳使用结束时间（与券商一致）：10:30, 11:30, 14:00, 15:00
    """
    df = df[_in_trading_hours(df["timestamp"])].copy()
    df = df.sort_values("timestamp").reset_index(drop=True)

    df["date"] = df["timestamp"].dt.date

    # 分配 bar 编号：每个交易时段内按 60min 切分
    # 早盘 9:30-11:30 = 121 根 1min bar → 60 + 61
    # 午盘 13:00-15:00 = 121 根 1min bar → 60 + 61
    time_val = df["timestamp"].dt.hour * 100 + df["timestamp"].dt.minute

    df["_bar_id"] = np.select(
        [
            time_val.between(930, 1029),
            time_val.between(1030, 1130),
            time_val.between(1300, 1359),
            time_val.between(1400, 1500),
        ],
        [0, 1, 2, 3],
        default=-1,
    )

    result = df.groupby(["date", "_bar_id"], sort=False).agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
        "amount": "sum",
        "timestamp": "first",
    }).reset_index(drop=True)

    # 时间戳改为结束时间（+1h），与券商标记一致
    result["timestamp"] = result["timestamp"] + pd.Timedelta(hours=1)

    result = result.sort_values("timestamp").reset_index(drop=True)
    return result[_KLINE_COLS]


def _resample_by_session(df: pd.DataFrame) -> pd.DataFrame:
    """按 A 股交易时段聚合为 120min K 线。

    早盘 9:30-11:30 和午盘 13:00-15:00 各产生一根 K 线。
    """
    df = df[_in_trading_hours(df["timestamp"])].copy()
    df = df.sort_values("timestamp").reset_index(drop=True)

    df["date"] = df["timestamp"].dt.date

    # 标记早盘 (< 12:00) 和午盘 (>= 12:00)
    df["session_id"] = np.where(df["timestamp"].dt.hour < 12, "morning", "afternoon")

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

    result = result.sort_values("timestamp").reset_index(drop=True)
    return result[_KLINE_COLS]


def _resample_daily(df: pd.DataFrame) -> pd.DataFrame:
    """日线聚合。若数据已经是日线格式则直接返回，否则从分钟线聚合。"""
    if _is_daily_data(df["timestamp"]):
        return df[[c for c in _KLINE_COLS if c in df.columns]].copy()

    df = df[_in_trading_hours(df["timestamp"])].copy()
    if df.empty:
        return pd.DataFrame(columns=_KLINE_COLS)

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

    result["timestamp"] = result["timestamp"].dt.normalize()

    return result.sort_values("timestamp").reset_index(drop=True)[_KLINE_COLS]


def _resample_weekly(df: pd.DataFrame) -> pd.DataFrame:
    """周线聚合。基于交易日数据，按自然周分组。"""
    daily = _resample_daily(df)
    if daily.empty:
        return daily

    daily["_week_key"] = daily["timestamp"].dt.strftime("%Y-W%V")

    result = daily.groupby("_week_key").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
        "amount": "sum",
        "timestamp": "last",
    }).reset_index(drop=True)

    ts = result["timestamp"]
    # 将时间戳对齐到当周周五（dayofweek=4）
    result["timestamp"] = (ts + pd.to_timedelta((4 - ts.dt.dayofweek) % 7, unit="D")).dt.normalize()
    return result.sort_values("timestamp").reset_index(drop=True)[_KLINE_COLS]


def _resample_monthly(df: pd.DataFrame) -> pd.DataFrame:
    """月线聚合。基于交易日数据，按年-月分组。"""
    daily = _resample_daily(df)
    if daily.empty:
        return daily

    daily["_month_key"] = daily["timestamp"].dt.strftime("%Y-%m")

    result = daily.groupby("_month_key", as_index=False).agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
        "amount": "sum",
    })

    result["timestamp"] = result["_month_key"].apply(lambda x: pd.Timestamp(x) + pd.offsets.MonthEnd(0))
    result = result.drop(columns="_month_key")
    return result.sort_values("timestamp").reset_index(drop=True)[_KLINE_COLS]


def _resample_quarterly(df: pd.DataFrame) -> pd.DataFrame:
    """季线聚合。基于交易日数据，按年-季分组。"""
    daily = _resample_daily(df)
    if daily.empty:
        return daily

    daily["_quarter_key"] = daily["timestamp"].dt.to_period("Q").astype(str)

    result = daily.groupby("_quarter_key", as_index=False).agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
        "amount": "sum",
    })

    result["timestamp"] = result["_quarter_key"].apply(lambda x: pd.Period(x).end_time.normalize())
    result = result.drop(columns="_quarter_key")
    return result.sort_values("timestamp").reset_index(drop=True)[_KLINE_COLS]


def resample_kline(kline_df: pd.DataFrame, period: str) -> pd.DataFrame:
    """重采样K线数据到不同周期

    Args:
        kline_df: K线数据，包含列: timestamp, open, high, low, close, volume, amount
        period: 目标周期，支持 "1min", "5min", "15min", "30min", "60min", "120min",
                "1D", "1W", "1M", "1Q"

    Returns:
        重采样后的K线数据
    """
    if len(kline_df) == 0 or period == "1min":
        return kline_df.copy()

    df = kline_df
    if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
        df = kline_df.copy()
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

    elif period == "60min":
        result = _resample_60min(df)

    elif period == "120min":
        result = _resample_by_session(df)

    else:
        # 分钟线重采样（5min, 15min, 30min）
        # closed='left'/label='right'：[9:30, 9:35) 标记为 9:35，与券商 bar 结束时间一致
        df_indexed = df.set_index('timestamp')

        offset = PERIOD_MAP[period]
        resampled = df_indexed.resample(
            rule=offset,
            closed='left',
            label='right'
        ).agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum',
            'amount': 'sum',
        })

        resampled = resampled.reset_index()

        # A股交易时段过滤：保留 bar 结束时间落在交易时段内的行
        def get_valid_ends(p: str) -> set[int]:
            if p == "5min":
                return set(range(935, 1131, 5)) | set(range(1305, 1501, 5))
            elif p == "15min":
                return {945, 1000, 1015, 1030, 1045, 1100, 1115, 1130,
                        1315, 1330, 1345, 1400, 1415, 1430, 1445, 1500}
            elif p == "30min":
                return {1000, 1030, 1100, 1130, 1330, 1400, 1430, 1500}
            return set()

        valid_ends = get_valid_ends(period)
        tv = resampled['timestamp'].dt.hour * 100 + resampled['timestamp'].dt.minute
        resampled = resampled[tv.isin(valid_ends)]
        resampled = resampled.dropna()
        result = resampled.reset_index(drop=True)

    return result

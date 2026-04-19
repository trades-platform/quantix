"""价格复权模块"""

import pandas as pd


def apply_factor(
    kline_df: pd.DataFrame,
    factor_df: pd.DataFrame,
    mode: str = "hfq",
) -> pd.DataFrame:
    """应用复权因子到K线数据

    Args:
        kline_df: K线数据，包含列: timestamp, open, high, low, close, volume, amount
        factor_df: 后复权因子数据，包含列: timestamp, factor (仅包含变化点)
        mode: 复权方式
            - "hfq": 后复权，adjusted = raw * factor（价格随时间增长）
            - "qfq": 前复权，adjusted = raw * factor / latest_factor（最新价不变，历史下调）
            - "none": 不复权，直接返回原始数据

    Returns:
        包含原始列和调整后列 (adjusted_open/high/low/close) 的DataFrame
    """
    # 创建结果副本
    result = kline_df.copy()

    # 确保 timestamp 列是 datetime 类型
    if not pd.api.types.is_datetime64_any_dtype(result['timestamp']):
        result['timestamp'] = pd.to_datetime(result['timestamp'])

    if mode == "none" or factor_df.empty:
        result['adjusted_open'] = result['open']
        result['adjusted_high'] = result['high']
        result['adjusted_low'] = result['low']
        result['adjusted_close'] = result['close']
        return result

    # 准备因子数据
    factor_copy = factor_df.copy()
    if not pd.api.types.is_datetime64_any_dtype(factor_copy['timestamp']):
        factor_copy['timestamp'] = pd.to_datetime(factor_copy['timestamp'])

    # 使用 merge_asof 进行前向填充
    merged = pd.merge_asof(
        result.sort_values('timestamp'),
        factor_copy.sort_values('timestamp').rename(columns={'factor': '_factor'}),
        on='timestamp',
        direction='backward'
    )

    # 填充 NaN（早于第一个因子点的数据使用第一个因子值）
    if merged['_factor'].isna().any():
        first_factor = factor_copy['factor'].iloc[0]
        merged['_factor'] = merged['_factor'].fillna(first_factor)

    if mode == "hfq":
        # 后复权：adjusted = raw * factor
        scale = merged['_factor']
    elif mode == "qfq":
        # 前复权：adjusted = raw * factor / latest_factor
        latest_factor = merged['_factor'].iloc[-1]
        scale = merged['_factor'] / latest_factor
    else:
        raise ValueError(f"Invalid adjust mode: {mode}, expected 'none', 'qfq', or 'hfq'")

    result['adjusted_open'] = result['open'] * scale
    result['adjusted_high'] = result['high'] * scale
    result['adjusted_low'] = result['low'] * scale
    result['adjusted_close'] = result['close'] * scale

    return result

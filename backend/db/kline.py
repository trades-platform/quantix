"""LanceDB K线数据操作层"""

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pyarrow as pa

from backend.db.lancedb import get_kline_db
from backend.db.sqlite import SessionLocal
from backend.models import Symbol

# K线数据表 Schema
KLINE_SCHEMA = pa.schema(
    [
        pa.field("timestamp", pa.timestamp("us")),
        pa.field("open", pa.float64()),
        pa.field("high", pa.float64()),
        pa.field("low", pa.float64()),
        pa.field("close", pa.float64()),
        pa.field("volume", pa.int64()),
        pa.field("amount", pa.float64()),
    ]
)


def get_table_name(symbol: str) -> str:
    """获取标的对应的表名"""
    return f"kline_{symbol.replace('.', '_')}"


def _get_table_list(db) -> list[str]:
    """获取数据库中的表名列表（兼容 LanceDB API 变更）"""
    tables = db.list_tables()
    return tables.tables if hasattr(tables, 'tables') else list(tables)


def import_kline(symbol: str, data: pd.DataFrame) -> int:
    """导入K线数据到 LanceDB

    Args:
        symbol: 标的代码
        data: K线数据 DataFrame，需包含列:
              - timestamp: datetime
              - open, high, low, close: float
              - volume: int
              - amount: float (可选)

    Returns:
        导入的行数
    """
    db = get_kline_db()
    table_name = get_table_name(symbol)

    # 确保数据列名正确
    required_cols = ["timestamp", "open", "high", "low", "close", "volume"]
    for col in required_cols:
        if col not in data.columns:
            raise ValueError(f"Missing required column: {col}")

    if "amount" not in data.columns:
        data["amount"] = 0.0

    # 确保 timestamp 是 datetime 类型
    if not pd.api.types.is_datetime64_any_dtype(data["timestamp"]):
        data["timestamp"] = pd.to_datetime(data["timestamp"])

    # 按时间排序并去重
    data = data.sort_values("timestamp").drop_duplicates(subset=["timestamp"])

    # 创建或打开表
    if table_name not in _get_table_list(db):
        table = db.create_table(table_name, schema=KLINE_SCHEMA)
    else:
        table = db.open_table(table_name)

    # 删除重复时间的数据（避免重复导入）
    existing = table.to_pandas()["timestamp"] if table.count_rows() > 0 else pd.Series(dtype="datetime64[ns]")
    new_data = data[~data["timestamp"].isin(existing)]

    if len(new_data) > 0:
        table.add(new_data)

        # Upsert Symbol metadata after successful import
        with SessionLocal() as session:
            existing = session.query(Symbol).filter(Symbol.symbol == symbol).first()
            total_rows = table.count_rows()
            ts_min = data["timestamp"].min()
            ts_max = data["timestamp"].max()
            if existing:
                existing.latest_timestamp = ts_max
                if not existing.earliest_timestamp or existing.earliest_timestamp.year == 1970:
                    existing.earliest_timestamp = ts_min
                else:
                    existing.earliest_timestamp = min(existing.earliest_timestamp, ts_min)
                existing.row_count = total_rows
                existing.updated_at = datetime.now(timezone.utc)
            else:
                session.add(Symbol(
                    symbol=symbol,
                    earliest_timestamp=ts_min,
                    latest_timestamp=ts_max,
                    row_count=total_rows,
                ))
            session.commit()

    return len(new_data)


def _query_kline(
    symbol: str,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> pd.DataFrame:
    """查询K线数据

    Args:
        symbol: 标的代码
        start_date: 开始日期（包含）
        end_date: 结束日期（包含）

    Returns:
        K线数据 DataFrame
    """
    db = get_kline_db()
    table_name = get_table_name(symbol)

    if table_name not in _get_table_list(db):
        return pd.DataFrame()

    table = db.open_table(table_name)

    # 查询全量数据后在 pandas 侧过滤（LanceDB timestamp filter 兼容性差）
    data = table.to_pandas()

    if start_date:
        data = data[data["timestamp"] >= pd.Timestamp(start_date)]
    if end_date:
        data = data[data["timestamp"] <= pd.Timestamp(end_date)]

    return data.sort_values("timestamp").reset_index(drop=True)


def list_symbols() -> list[str]:
    """获取已有K线数据的标的列表

    Returns:
        标的代码列表
    """
    # Try querying from Symbol model first
    with SessionLocal() as session:
        symbols = [s.symbol for s in session.query(Symbol.symbol).all()]
        if symbols:
            return sorted(symbols)

    # Fallback to LanceDB scan if no records found
    db = get_kline_db()
    table_names = _get_table_list(db)

    # 从表名提取标的代码
    symbols = []
    for name in table_names:
        if name.startswith("kline_"):
            symbol = name[6:].replace("_", ".")
            symbols.append(symbol)

    return sorted(symbols)


def _query_kline_batch(
    symbols: list[str],
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> dict[str, pd.DataFrame]:
    """批量查询多个标的的 K 线数据

    Args:
        symbols: 标的代码列表
        start_date: 开始日期（包含）
        end_date: 结束日期（包含）

    Returns:
        {symbol: DataFrame} 字典，跳过无数据的标的
    """
    result = {}
    for symbol in symbols:
        df = _query_kline(symbol, start_date, end_date)
        if not df.empty:
            result[symbol] = df
    return result


def get_market_data(
    symbols: str | list[str],
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    period: str = "1min",
    adjust: str = "none",
) -> dict[str, pd.DataFrame]:
    """统一行情数据获取接口

    从 LanceDB 获取 K 线数据，可选复权和重采样。

    数据处理流水线：原始 1min → 复权(adjust≠none) → 重采样(period≠1min)

    Args:
        symbols: 单个标的代码或标的列表
        start_date: 开始日期（包含）
        end_date: 结束日期（包含）
        period: K 线周期，支持 "1min", "5min", "15min", "30min", "60min", "1D"
        adjust: 复权方式，"none" 不复权，"hfq" 后复权，"qfq" 前复权

    Returns:
        {symbol: DataFrame} 字典
    """
    from backend.db.factor import _query_factor
    from backend.engine.adjust import apply_factor
    from backend.engine.resample import resample_kline

    if isinstance(symbols, str):
        symbols = [symbols]

    valid_adjust = ("none", "hfq", "qfq")
    if adjust not in valid_adjust:
        raise ValueError(f"Invalid adjust: {adjust}, expected one of {valid_adjust}")

    data_dict = _query_kline_batch(symbols, start_date, end_date)

    for symbol, df in data_dict.items():
        if df.empty:
            continue

        # 复权
        if adjust != "none":
            factor_df = _query_factor(symbol)
            if not factor_df.empty:
                df = apply_factor(df, factor_df, mode=adjust)
                for col in ["open", "high", "low", "close"]:
                    df[col] = df[f"adjusted_{col}"]
                data_dict[symbol] = df

        # 重采样
        if period != "1min":
            data_dict[symbol] = resample_kline(data_dict[symbol], period)

    return data_dict

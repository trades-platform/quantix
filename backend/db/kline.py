"""LanceDB K线数据操作层"""

from datetime import datetime
from pathlib import Path

import pandas as pd
import pyarrow as pa

from backend.db.lancedb import get_kline_db

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

    return len(new_data)


def query_kline(
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

    # 构建过滤条件
    filters = []
    if start_date:
        filters.append(f"timestamp >= '{start_date.isoformat()}'")
    if end_date:
        filters.append(f"timestamp <= '{end_date.isoformat()}'")

    filter_str = " AND ".join(filters) if filters else None

    # 查询数据
    if filter_str:
        data = table.to_pandas(filter=filter_str)
    else:
        data = table.to_pandas()

    return data.sort_values("timestamp").reset_index(drop=True)


def list_symbols() -> list[str]:
    """获取已有K线数据的标的列表

    Returns:
        标的代码列表
    """
    db = get_kline_db()
    table_names = _get_table_list(db)

    # 从表名提取标的代码
    symbols = []
    for name in table_names:
        if name.startswith("kline_"):
            symbol = name[6:].replace("_", ".")
            symbols.append(symbol)

    return sorted(symbols)

"""LanceDB 后复权因子数据操作层"""

import re
from datetime import datetime

import pandas as pd
import pyarrow as pa

from backend.db.lancedb import get_kline_db

_SYMBOL_RE = re.compile(r"^[A-Za-z0-9.]+$")

FACTOR_TABLE = "factor"

# 因子数据表 Schema（单表，所有标的共享）
FACTOR_SCHEMA = pa.schema([
    pa.field("symbol", pa.utf8()),
    pa.field("timestamp", pa.timestamp("us")),
    pa.field("factor", pa.float64()),
])


def _get_table_list(db) -> list[str]:
    """获取数据库中的表名列表（兼容 LanceDB API 变更）"""
    tables = db.list_tables()
    return tables.tables if hasattr(tables, 'tables') else list(tables)


def _compress_factor(df: pd.DataFrame) -> pd.DataFrame:
    """压缩因子数据：只保留因子值发生变化的行（按标的分组）"""
    if df.empty:
        return df
    df = df.sort_values(["symbol", "timestamp"]).drop_duplicates(
        subset=["symbol", "timestamp"], keep="last"
    )
    # 每个标的内只保留 factor 变化的行
    mask = df.groupby("symbol")["factor"].diff() != 0
    return df[mask].copy()


def import_factor(symbol: str, data: pd.DataFrame) -> int:
    """导入后复权因子数据到 LanceDB

    Args:
        symbol: 标的代码，如 "600000.SH"
        data: 因子 DataFrame，需包含列:
              - timestamp: datetime
              - factor: float

    Returns:
        导入的行数（压缩后）

    Note:
        非并发安全：每次导入会读取全表、drop 旧表、create 新表。
        多进程同时调用 import_factor 会丢失数据，调用方需确保串行。
    """
    db = get_kline_db()

    for col in ["timestamp", "factor"]:
        if col not in data.columns:
            raise ValueError(f"Missing required column: {col}")

    if not pd.api.types.is_datetime64_any_dtype(data["timestamp"]):
        data["timestamp"] = pd.to_datetime(data["timestamp"])

    data = data.dropna(subset=["factor"])
    new_rows = data[["timestamp", "factor"]].copy()
    new_rows["symbol"] = symbol

    if FACTOR_TABLE in _get_table_list(db):
        table = db.open_table(FACTOR_TABLE)
        existing_df = table.to_pandas() if table.count_rows() > 0 else pd.DataFrame()

        if not existing_df.empty:
            # 删除该标的旧数据，合并新数据
            existing_df = existing_df[existing_df["symbol"] != symbol]
            combined = pd.concat([existing_df, new_rows], ignore_index=True)
        else:
            combined = new_rows

        db.drop_table(FACTOR_TABLE)
    else:
        combined = new_rows

    compressed = _compress_factor(combined)

    if len(compressed) > 0:
        db.create_table(FACTOR_TABLE, compressed, schema=FACTOR_SCHEMA)
        return len(compressed[compressed["symbol"] == symbol])
    return 0


def query_factor(
    symbol: str,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> pd.DataFrame:
    """查询后复权因子数据

    Args:
        symbol: 标的代码
        start_date: 开始日期（包含）
        end_date: 结束日期（包含）

    Returns:
        因子数据 DataFrame
    """
    if not _SYMBOL_RE.match(symbol):
        raise ValueError(f"Invalid symbol: {symbol}")

    db = get_kline_db()

    if FACTOR_TABLE not in _get_table_list(db):
        return pd.DataFrame()

    table = db.open_table(FACTOR_TABLE)

    filters = [f"symbol = '{symbol}'"]
    if start_date:
        filters.append(f"timestamp >= '{start_date.isoformat()}'")
    if end_date:
        filters.append(f"timestamp <= '{end_date.isoformat()}'")

    filter_str = " AND ".join(filters)
    data = table.search().where(filter_str).to_pandas()
    if "symbol" in data.columns:
        data = data[["symbol", "timestamp", "factor"]]

    return data.sort_values("timestamp").reset_index(drop=True)


def list_factor_symbols() -> list[str]:
    """获取已有因子数据的标的列表

    Returns:
        标的代码列表
    """
    db = get_kline_db()

    if FACTOR_TABLE not in _get_table_list(db):
        return []

    table = db.open_table(FACTOR_TABLE)
    df = table.search().select(["symbol"]).to_pandas()
    return sorted(df["symbol"].unique().tolist())

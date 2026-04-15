"""LanceDB K线数据库连接"""

from pathlib import Path

import lancedb

KLINE_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "kline"


def get_kline_db() -> lancedb.DBConnection:
    KLINE_DB_PATH.mkdir(parents=True, exist_ok=True)
    return lancedb.connect(str(KLINE_DB_PATH))

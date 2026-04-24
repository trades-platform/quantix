"""LanceDB K线数据库连接"""

from pathlib import Path

try:
    import lancedb  # type: ignore[import-not-found]
except ModuleNotFoundError:
    class _MissingLanceDB:
        def connect(self, *_args, **_kwargs):
            raise ModuleNotFoundError(
                "缺少可选依赖 lancedb，请先安装或激活包含该依赖的环境"
            )

    lancedb = _MissingLanceDB()

KLINE_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "kline"


def get_kline_db():
    KLINE_DB_PATH.mkdir(parents=True, exist_ok=True)
    return lancedb.connect(str(KLINE_DB_PATH))

"""AmazingData K线数据获取"""

import logging
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

import AmazingData as AD
from backend.data.config import get_tgw_credentials
from backend.data.pandas_compat import patch_fillna, restore_fillna
from backend.db import import_kline as db_import_kline
from backend.db import import_factor as db_import_factor
from backend.db import query_kline as db_query_kline

logger = logging.getLogger(__name__)

_logged_in = False

TGW_CACHE_PATH = str(Path(__file__).resolve().parents[2] / "data" / "tgw_cachebasedata")


def _ensure_login():
    """确保已登录 TGW"""
    global _logged_in
    if _logged_in:
        return
    creds = get_tgw_credentials()
    try:
        AD.login(
            creds["username"],
            creds["password"],
            creds["host"],
            creds["port"],
        )
    except SystemExit:
        raise RuntimeError("TGW 登录失败，请检查网络连接和配置信息")
    _logged_in = True


# ---- K-line helpers ----


def _convert_df(df: pd.DataFrame) -> pd.DataFrame:
    """转换 AmazingData DataFrame 为 LanceDB 格式"""
    if df is None or df.empty:
        return df

    rename_map = {
        "kline_time": "timestamp",
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "volume": "volume",
        "amount": "amount",
    }

    result = df[list(rename_map.keys())].rename(columns=rename_map)

    if "timestamp" in result.columns and not pd.api.types.is_datetime64_any_dtype(
        result["timestamp"]
    ):
        result["timestamp"] = pd.to_datetime(result["timestamp"])

    return result


def _date_to_int(date: str | datetime) -> int:
    """转换为 YYYYMMDD 整数"""
    if isinstance(date, str):
        return int(datetime.strptime(date, "%Y-%m-%d").strftime("%Y%m%d"))
    return int(date.strftime("%Y%m%d"))


# ---- Factor helpers ----


def _convert_factor_raw(raw_df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """将 AmazingData 宽格式因子 DataFrame 转换为每个标的的 DataFrame 字典"""
    if raw_df is None or raw_df.empty:
        return {}

    raw_df.index = pd.to_datetime(raw_df.index)
    result = {}
    for col in raw_df.columns:
        symbol_df = pd.DataFrame({
            "timestamp": raw_df.index,
            "factor": raw_df[col].values,
        })
        symbol_df = symbol_df.dropna(subset=["factor"])
        result[col] = symbol_df

    return result


# ---- K-line fetch ----


def fetch_kline(
    symbol: str,
    period: int = AD.constant.Period.min1.value,
    start_date: str | datetime | None = None,
    end_date: str | datetime | None = None,
    increment: bool = False,
    use_subprocess: bool = False,
) -> int:
    """获取并导入K线数据

    Args:
        symbol: 标的代码，如 "600000.SH"
        period: K线周期，默认 1分钟
        start_date: 开始日期 (YYYY-MM-DD)
        end_date: 结束日期 (YYYY-MM-DD)
        increment: 是否增量导入（从最新数据时间到当前）
        use_subprocess: 是否在子进程中执行 TGW 操作（Web API 用）

    Returns:
        导入的行数
    """
    if increment:
        existing_data = db_query_kline(symbol)
        if len(existing_data) > 0:
            latest = existing_data["timestamp"].max()
            start_date = latest + pd.Timedelta(minutes=1)
        else:
            raise ValueError(f"标的 {symbol} 无现有数据，无法增量导入")

        end_date = datetime.now()

    if start_date is None or end_date is None:
        raise ValueError("start_date 和 end_date 不能为空，除非使用 --increment")

    if use_subprocess:
        count = _fetch_kline_subprocess(symbol, period, start_date, end_date)
    else:
        count = _fetch_kline_direct(symbol, period, start_date, end_date)

    # 自动获取 factor 数据
    try:
        fetch_factor(symbol, use_subprocess=use_subprocess)
    except Exception as e:
        logger.warning("获取 %s 因子数据失败: %s", symbol, e)
        print(f"  警告: 获取 {symbol} 因子数据失败: {e}", file=sys.stderr)

    return count


def _fetch_kline_direct(symbol, period, start_date, end_date) -> int:
    """直接模式：login -> 查询 -> 导入（CLI 用）。"""
    _ensure_login()

    start_int = _date_to_int(start_date)
    end_int = _date_to_int(end_date)

    calendar = AD.BaseData().get_calendar()
    market = AD.MarketData(calendar)

    df_map = market.query_kline(
        [symbol],
        begin_date=start_int,
        end_date=end_int,
        period=period,
    )

    df = df_map.get(symbol)
    if df is None or df.empty:
        return 0

    df = _convert_df(df)
    return db_import_kline(symbol, df)


def _fetch_kline_subprocess(symbol, period, start_date, end_date) -> int:
    """子进程模式：在子进程获取数据，父进程导入 LanceDB。"""
    from backend.data.tgw_worker import fetch_kline_subprocess

    result = fetch_kline_subprocess(symbol, period, start_date, end_date)
    if not result.success:
        raise RuntimeError(result.error)
    if result.data is None:
        return 0
    return db_import_kline(symbol, result.data)


def fetch_increment(symbol: str, period: int = AD.constant.Period.min1.value) -> int:
    """增量导入 - 从最新数据时间到当前"""
    return fetch_kline(symbol, period, increment=True)


def get_code_list(data_type: str = "both", use_subprocess: bool = False) -> list[str]:
    """获取代码列表

    Args:
        data_type: "stock" | "etf" | "both"
        use_subprocess: 是否在子进程中执行（Web API 用）

    Returns:
        代码列表
    """
    if use_subprocess:
        from backend.data.tgw_worker import get_code_list_subprocess

        result = get_code_list_subprocess(data_type)
        if not result.success:
            raise RuntimeError(result.error)
        return result.data

    _ensure_login()

    base = AD.BaseData()

    if data_type == "stock":
        return base.get_code_list("EXTRA_STOCK_A_SH_SZ")
    elif data_type == "etf":
        return base.get_code_list("EXTRA_ETF")
    else:  # both
        stock_list = base.get_code_list("EXTRA_STOCK_A_SH_SZ")
        etf_list = base.get_code_list("EXTRA_ETF")
        return stock_list + etf_list


def fetch_all(
    data_type: str,
    period: int,
    start_date: str | datetime,
    end_date: str | datetime,
    progress: bool = True,
    use_subprocess: bool = False,
) -> dict:
    """批量获取并导入所有标的K线数据

    Args:
        data_type: "stock" | "etf" | "both"
        period: K线周期
        start_date: 开始日期
        end_date: 结束日期
        progress: 是否显示进度
        use_subprocess: 是否在子进程中执行

    Returns:
        {"success": [...], "failed": [...]} 每类包含 symbol 和 count
    """
    if not use_subprocess:
        _ensure_login()

    codes = get_code_list(data_type, use_subprocess=use_subprocess)

    results = {"success": [], "failed": []}

    for i, code in enumerate(codes):
        if progress:
            print(f"[{i+1}/{len(codes)}] 导入 {code}...", file=sys.stderr)

        try:
            count = fetch_kline(code, period, start_date, end_date, use_subprocess=use_subprocess)
            results["success"].append({"symbol": code, "count": count})
        except Exception as e:
            results["failed"].append({"symbol": code, "error": str(e)})

    # 批量获取所有成功标的的 factor 数据
    success_symbols = [r["symbol"] for r in results["success"]]
    if success_symbols:
        try:
            fetch_factor_batch(success_symbols, use_subprocess=use_subprocess, progress=progress)
        except Exception as e:
            logger.warning("批量获取因子数据失败: %s", e)
            print(f"警告: 批量获取因子数据失败: {e}", file=sys.stderr)

    return results


# ---- Factor fetch ----


def fetch_factor(
    symbol: str,
    use_subprocess: bool = False,
) -> int:
    """获取并导入后复权因子数据

    Args:
        symbol: 标的代码，如 "600000.SH"
        use_subprocess: 是否在子进程中执行

    Returns:
        导入的行数（压缩后）
    """
    if use_subprocess:
        return _fetch_factor_subprocess(symbol)
    else:
        return _fetch_factor_direct(symbol)


def _fetch_factor_direct(symbol: str) -> int:
    """直接模式获取因子数据"""
    _ensure_login()

    original = patch_fillna()
    try:
        base = AD.BaseData()
        raw_df = base.get_backward_factor([symbol], local_path=TGW_CACHE_PATH, is_local=False)
    finally:
        restore_fillna(original)

    factor_dict = _convert_factor_raw(raw_df)
    if symbol not in factor_dict:
        return 0

    return db_import_factor(symbol, factor_dict[symbol])


def _fetch_factor_subprocess(symbol: str) -> int:
    """子进程模式获取因子数据"""
    from backend.data.tgw_worker import fetch_factor_subprocess

    result = fetch_factor_subprocess([symbol])
    if not result.success:
        raise RuntimeError(result.error)
    if result.data is None or symbol not in result.data:
        return 0

    return db_import_factor(symbol, result.data[symbol])


def fetch_factor_batch(
    symbols: list[str],
    use_subprocess: bool = False,
    progress: bool = True,
) -> dict:
    """批量获取并导入后复权因子数据

    一次 API 调用获取所有标的因子，然后逐个导入。

    Args:
        symbols: 标的代码列表
        use_subprocess: 是否在子进程中执行
        progress: 是否显示进度

    Returns:
        {"success": [...], "failed": [...]}
    """
    results = {"success": [], "failed": []}

    if use_subprocess:
        from backend.data.tgw_worker import fetch_factor_subprocess

        try:
            result = fetch_factor_subprocess(symbols)
            if not result.success:
                raise RuntimeError(result.error)
            factor_dict = result.data or {}
        except Exception as e:
            for sym in symbols:
                results["failed"].append({"symbol": sym, "error": str(e)})
            return results
    else:
        _ensure_login()
        original = patch_fillna()
        try:
            base = AD.BaseData()
            raw_df = base.get_backward_factor(symbols, local_path=TGW_CACHE_PATH, is_local=False)
            factor_dict = _convert_factor_raw(raw_df)
        except Exception as e:
            for sym in symbols:
                results["failed"].append({"symbol": sym, "error": str(e)})
            return results
        finally:
            restore_fillna(original)

    for i, symbol in enumerate(symbols):
        if progress:
            print(f"[{i+1}/{len(symbols)}] 导入因子 {symbol}...", file=sys.stderr)
        if symbol in factor_dict:
            try:
                count = db_import_factor(symbol, factor_dict[symbol])
                results["success"].append({"symbol": symbol, "count": count})
            except Exception as e:
                results["failed"].append({"symbol": symbol, "error": str(e)})
        else:
            results["failed"].append({"symbol": symbol, "error": "无因子数据"})

    return results


def fetch_factor_all(
    data_type: str = "both",
    use_subprocess: bool = False,
    progress: bool = True,
) -> dict:
    """获取所有股票/ETF的后复权因子数据"""
    codes = get_code_list(data_type, use_subprocess=use_subprocess)
    return fetch_factor_batch(codes, use_subprocess=use_subprocess, progress=progress)

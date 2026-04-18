"""AmazingData TGW 子进程隔离层。

每次 TGW 操作（login -> 查询 -> logout）运行在独立子进程中，
确保父进程（FastAPI）永不调用 AD.login()。
"""

import logging
import traceback
from dataclasses import dataclass
from datetime import datetime
from multiprocessing import get_context
from pathlib import Path
from queue import Empty

import pandas as pd

from backend.data.config import get_tgw_credentials

logger = logging.getLogger(__name__)

DEFAULT_FETCH_TIMEOUT = 120
KILL_GRACE_PERIOD = 5


@dataclass
class TgwResult:
    """子进程操作的序列化结果。"""

    success: bool
    data: object = None  # DataFrame 或 list[str]
    error: str | None = None
    row_count: int = 0


def _date_to_int(date: str | datetime) -> int:
    """转换为 YYYYMMDD 整数。"""
    if isinstance(date, str):
        return int(datetime.strptime(date, "%Y-%m-%d").strftime("%Y%m%d"))
    return int(date.strftime("%Y%m%d"))


def _convert_df(df: pd.DataFrame) -> pd.DataFrame:
    """转换 AmazingData DataFrame 为 LanceDB 格式。"""
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


# ---- Worker 函数（在子进程中运行） ----


def _worker_kline(
    result_queue,
    symbol: str,
    period: int,
    start_int: int,
    end_int: int,
):
    """子进程：login -> 获取 kline -> logout -> 通过 Queue 返回 DataFrame。"""
    import AmazingData as AD

    creds = get_tgw_credentials()
    username = creds["username"]
    try:
        AD.login(creds["username"], creds["password"], creds["host"], creds["port"])
    except SystemExit:
        result_queue.put(TgwResult(success=False, error="TGW 登录失败，请检查网络连接和配置信息"))
        return
    except Exception as e:
        result_queue.put(TgwResult(success=False, error=f"TGW 登录异常: {e}"))
        return

    try:
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
            result_queue.put(TgwResult(success=True, data=None, row_count=0))
        else:
            converted = _convert_df(df)
            result_queue.put(
                TgwResult(success=True, data=converted, row_count=len(converted))
            )
    except Exception as e:
        result_queue.put(TgwResult(success=False, error=f"TGW 查询异常: {e}\n{traceback.format_exc()}"))
    finally:
        try:
            AD.logout(username)
        except Exception:
            pass


def _worker_code_list(result_queue, data_type: str):
    """子进程：login -> 获取代码列表 -> logout -> 通过 Queue 返回列表。"""
    import AmazingData as AD

    creds = get_tgw_credentials()
    username = creds["username"]
    try:
        AD.login(creds["username"], creds["password"], creds["host"], creds["port"])
    except SystemExit:
        result_queue.put(TgwResult(success=False, error="TGW 登录失败，请检查网络连接和配置信息"))
        return
    except Exception as e:
        result_queue.put(TgwResult(success=False, error=f"TGW 登录异常: {e}"))
        return

    try:
        base = AD.BaseData()
        if data_type == "stock":
            codes = base.get_code_list("EXTRA_STOCK_A_SH_SZ")
        elif data_type == "etf":
            codes = base.get_code_list("EXTRA_ETF")
        else:
            stock_list = base.get_code_list("EXTRA_STOCK_A_SH_SZ")
            etf_list = base.get_code_list("EXTRA_ETF")
            codes = stock_list + etf_list
        result_queue.put(TgwResult(success=True, data=codes))
    except Exception as e:
        result_queue.put(TgwResult(success=False, error=f"TGW 查询异常: {e}\n{traceback.format_exc()}"))
    finally:
        try:
            AD.logout(username)
        except Exception:
            pass


def _worker_factor(result_queue, code_list: list[str]):
    """子进程：login -> 获取后复权因子 -> logout -> 通过 Queue 返回结果。"""
    import AmazingData as AD

    from backend.data.pandas_compat import patch_fillna, restore_fillna

    original = patch_fillna()

    creds = get_tgw_credentials()
    username = creds["username"]
    try:
        AD.login(creds["username"], creds["password"], creds["host"], creds["port"])
    except SystemExit:
        result_queue.put(TgwResult(success=False, error="TGW 登录失败"))
        return
    except Exception as e:
        result_queue.put(TgwResult(success=False, error=f"TGW 登录异常: {e}"))
        return

    try:
        local_path = str(Path(__file__).resolve().parents[2] / "data" / "tgw_cachebasedata")
        base = AD.BaseData()
        raw_df = base.get_backward_factor(code_list, local_path=local_path, is_local=False)

        if raw_df is None or raw_df.empty:
            result_queue.put(TgwResult(success=True, data={}))
            return

        # Convert wide DataFrame to dict of per-symbol DataFrames
        result = {}
        raw_df.index = pd.to_datetime(raw_df.index)
        for col in raw_df.columns:
            symbol_df = pd.DataFrame({
                "timestamp": raw_df.index,
                "factor": raw_df[col].values,
            })
            symbol_df = symbol_df.dropna(subset=["factor"])
            result[col] = symbol_df

        result_queue.put(TgwResult(success=True, data=result))
    except Exception as e:
        result_queue.put(TgwResult(success=False, error=f"TGW 查询异常: {e}\n{traceback.format_exc()}"))
    finally:
        restore_fillna(original)
        try:
            AD.logout(username)
        except Exception:
            pass


def _run_worker(target_fn, args: tuple, timeout: int = DEFAULT_FETCH_TIMEOUT) -> TgwResult:
    """启动子进程运行 target_fn，带超时处理。使用 spawn 创建干净进程。"""
    ctx = get_context("spawn")
    result_queue = ctx.Queue()
    process = ctx.Process(target=target_fn, args=(result_queue, *args))
    process.start()

    try:
        result = result_queue.get(timeout=timeout)
    except Empty:
        logger.error("TGW worker 超时 (%d 秒)", timeout)
        process.terminate()
        process.join(timeout=KILL_GRACE_PERIOD)
        if process.is_alive():
            process.kill()
            process.join(timeout=5)
        return TgwResult(success=False, error=f"操作超时 ({timeout} 秒)")
    finally:
        result_queue.close()
        process.join(timeout=KILL_GRACE_PERIOD + 10)
        if process.is_alive():
            process.kill()
            process.join(timeout=5)

    return result


# ---- 公开 API ----


def fetch_kline_subprocess(
    symbol: str,
    period: int,
    start_date: str | datetime,
    end_date: str | datetime,
    timeout: int = DEFAULT_FETCH_TIMEOUT,
) -> TgwResult:
    """在子进程中获取 kline 数据，返回 TgwResult。"""
    start_int = _date_to_int(start_date)
    end_int = _date_to_int(end_date)
    return _run_worker(_worker_kline, (symbol, period, start_int, end_int), timeout)


def get_code_list_subprocess(
    data_type: str = "both",
    timeout: int = DEFAULT_FETCH_TIMEOUT,
) -> TgwResult:
    """在子进程中获取代码列表，返回 TgwResult。"""
    return _run_worker(_worker_code_list, (data_type,), timeout)


def fetch_factor_subprocess(
    code_list: list[str],
    timeout: int = DEFAULT_FETCH_TIMEOUT,
) -> TgwResult:
    """在子进程中获取后复权因子数据，返回 TgwResult。"""
    return _run_worker(_worker_factor, (code_list,), timeout)

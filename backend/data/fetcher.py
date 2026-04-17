"""AmazingData K线数据获取"""

import sys
from datetime import datetime

import pandas as pd

import AmazingData as AD
from backend.data.config import get_tgw_credentials
from backend.db import import_kline as db_import_kline
from backend.db import query_kline as db_query_kline

_logged_in = False


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


def fetch_kline(
    symbol: str,
    period: int = AD.constant.Period.min1.value,
    start_date: str | datetime | None = None,
    end_date: str | datetime | None = None,
    increment: bool = False,
) -> int:
    """获取并导入K线数据

    Args:
        symbol: 标的代码，如 "600000.SH"
        period: K线周期，默认 1分钟
        start_date: 开始日期 (YYYY-MM-DD)
        end_date: 结束日期 (YYYY-MM-DD)
        increment: 是否增量导入（从最新数据时间到当前）

    Returns:
        导入的行数
    """
    _ensure_login()

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
    count = db_import_kline(symbol, df)

    return count


def fetch_increment(symbol: str, period: int = AD.constant.Period.min1.value) -> int:
    """增量导入 - 从最新数据时间到当前"""
    return fetch_kline(symbol, period, increment=True)


def get_code_list(data_type: str = "both") -> list[str]:
    """获取代码列表

    Args:
        data_type: "stock" | "etf" | "both"

    Returns:
        代码列表
    """
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
) -> dict:
    """批量获取并导入所有标的K线数据

    Args:
        data_type: "stock" | "etf" | "both"
        period: K线周期
        start_date: 开始日期
        end_date: 结束日期
        progress: 是否显示进度

    Returns:
        {"success": [...], "failed": [...]} 每类包含 symbol 和 count
    """
    _ensure_login()

    codes = get_code_list(data_type)

    results = {"success": [], "failed": []}

    for i, code in enumerate(codes):
        if progress:
            print(f"[{i+1}/{len(codes)}] 导入 {code}...", file=sys.stderr)

        try:
            count = fetch_kline(code, period, start_date, end_date)
            results["success"].append({"symbol": code, "count": count})
        except Exception as e:
            results["failed"].append({"symbol": code, "error": str(e)})

    return results
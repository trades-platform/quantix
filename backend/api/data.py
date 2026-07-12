"""数据管理 API"""

from datetime import datetime
from typing import List

from fastapi import APIRouter, HTTPException, UploadFile, status
from pydantic import BaseModel
import pandas as pd

from backend.db import SessionLocal, delete_symbol, import_kline, list_symbols, get_market_data
from backend.models import Symbol
from backend.plotting.serialize import (
    DEFAULT_LAYERS,
    _raw_to_layerspec,
    indicator_series_to_dict,
)

router = APIRouter(prefix="/data", tags=["data"])


class KlineImportRequest(BaseModel):
    symbol: str
    start_date: str
    end_date: str
    # CSV 格式数据或 JSON 格式数据
    data: List[dict]


class FetchKlineRequest(BaseModel):
    symbol: str
    period: str = "min1"
    start_date: str
    end_date: str


class FetchBatchRequest(BaseModel):
    symbols: list[str]
    period: str = "min1"
    start_date: str
    end_date: str


class SymbolResponse(BaseModel):
    symbol: str


@router.get("/symbols")
def get_symbols():
    """获取可用标的列表"""
    with SessionLocal() as db:
        symbols = db.query(Symbol).order_by(Symbol.symbol).all()
        return [
            {
                "symbol": s.symbol,
                "name": s.name,
                "data_type": s.data_type,
                "earliest_timestamp": s.earliest_timestamp.isoformat() if s.earliest_timestamp else None,
                "latest_timestamp": s.latest_timestamp.isoformat() if s.latest_timestamp else None,
                "row_count": s.row_count,
                "period": s.period,
                "updated_at": s.updated_at.isoformat() if s.updated_at else None,
            }
            for s in symbols
        ]


@router.delete("/symbols/{symbol}", status_code=status.HTTP_204_NO_CONTENT)
def delete_symbol_endpoint(symbol: str):
    """删除标的及其K线数据"""
    try:
        delete_symbol(symbol)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Symbol not found: {symbol}")


@router.get("/kline")
def get_kline_data(symbol: str, start_date: str | None = None, end_date: str | None = None, limit: int | None = None):
    """获取K线数据

    Args:
        symbol: 标的代码
        start_date: 开始日期 YYYY-MM-DD
        end_date: 结束日期 YYYY-MM-DD
        limit: 返回最近的 N 条数据
    """
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d") if start_date else None
        end_dt = datetime.strptime(end_date, "%Y-%m-%d") if end_date else None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")

    data_dict = get_market_data(symbol, start_dt, end_dt)
    data = data_dict.get(symbol, pd.DataFrame())

    # 限制返回条数（取最近的 N 条）
    if limit and limit > 0 and len(data) > limit:
        data = data.iloc[-limit:]

    # 转换为 JSON 友好格式
    df_out = data[["timestamp", "open", "high", "low", "close", "volume", "amount"]].copy()
    df_out["timestamp"] = df_out["timestamp"].astype(str)
    df_out["volume"] = df_out["volume"].astype(int)
    df_out["open"] = df_out["open"].astype(float)
    df_out["high"] = df_out["high"].astype(float)
    df_out["low"] = df_out["low"].astype(float)
    df_out["close"] = df_out["close"].astype(float)
    df_out["amount"] = df_out["amount"].astype(float)
    result = df_out.to_dict(orient="records")

    return {"symbol": symbol, "data": result}


class MarketDataRequest(BaseModel):
    symbols: list[str]
    start_date: str | None = None
    end_date: str | None = None
    period: str = "1min"
    adjust: str = "none"


@router.post("/market-data")
def get_market_data_api(req: MarketDataRequest):
    """统一行情数据接口

    支持多标的、复权、不同K线周期。
    """
    try:
        start_dt = datetime.strptime(req.start_date, "%Y-%m-%d") if req.start_date else None
        end_dt = datetime.strptime(req.end_date, "%Y-%m-%d") if req.end_date else None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")

    valid_periods = ("1min", "5min", "15min", "30min", "60min", "120min", "1D", "1W", "1M", "1Q")
    if req.period not in valid_periods:
        raise HTTPException(status_code=400, detail=f"Invalid period, supported: {valid_periods}")

    valid_adjust = ("none", "hfq", "qfq")
    if req.adjust not in valid_adjust:
        raise HTTPException(status_code=400, detail=f"Invalid adjust, supported: {valid_adjust}")

    data_dict = get_market_data(req.symbols, start_dt, end_dt, req.period, req.adjust)

    result = {}
    for symbol, df in data_dict.items():
        df_out = df[["timestamp", "open", "high", "low", "close", "volume", "amount"]].copy()
        df_out["timestamp"] = df_out["timestamp"].astype(str)
        df_out["volume"] = df_out["volume"].astype(int)
        df_out["open"] = df_out["open"].astype(float)
        df_out["high"] = df_out["high"].astype(float)
        df_out["low"] = df_out["low"].astype(float)
        df_out["close"] = df_out["close"].astype(float)
        df_out["amount"] = df_out["amount"].astype(float)
        result[symbol] = df_out.to_dict(orient="records")

    return {"data": result}


@router.post("/kline/import", status_code=status.HTTP_201_CREATED)
def import_kline_data(req: KlineImportRequest):
    """导入K线数据

    数据格式:
    [
        {"timestamp": "2024-01-01T00:00:00", "open": 10.0, "high": 11.0, "low": 9.5, "close": 10.5, "volume": 1000000},
        ...
    ]
    """
    try:
        df = pd.DataFrame(req.data)
        count = import_kline(req.symbol, df)
        return {"message": f"成功导入 {count} 条数据", "count": count}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导入失败: {e}")


@router.post("/kline/upload")
async def upload_kline_file(symbol: str, file: UploadFile):
    """上传 CSV 文件导入K线数据

    CSV 格式要求:
    timestamp,open,high,low,close,volume[,amount]
    """
    try:
        content = await file.read()
        df = pd.read_csv(pd.io.common.BytesIO(content))

        count = import_kline(symbol, df)
        return {"message": f"成功导入 {count} 条数据", "count": count}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"文件解析失败: {e}")


@router.post("/kline/fetch")
def fetch_kline_data(req: FetchKlineRequest):
    """从远程获取并导入K线数据"""
    from backend.data import fetch_kline as data_fetch_kline
    import AmazingData as AD

    period_map = {
        "min1": AD.constant.Period.min1.value,
        "min5": AD.constant.Period.min5.value,
        "min15": AD.constant.Period.min15.value,
        "min30": AD.constant.Period.min30.value,
        "min60": AD.constant.Period.min60.value,
        "day": AD.constant.Period.day.value,
        "week": AD.constant.Period.week.value,
        "month": AD.constant.Period.month.value,
    }
    if req.period not in period_map:
        raise HTTPException(status_code=400, detail=f"Invalid period: {req.period}")

    try:
        count = data_fetch_kline(req.symbol, period_map[req.period], req.start_date, req.end_date, use_subprocess=True)
        return {"symbol": req.symbol, "count": count, "message": "导入完成"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/kline/fetch-batch")
def fetch_batch_data(req: FetchBatchRequest):
    """批量从远程获取并导入K线数据"""
    from backend.data import fetch_kline as data_fetch_kline
    import AmazingData as AD

    period_map = {
        "min1": AD.constant.Period.min1.value,
        "min5": AD.constant.Period.min5.value,
        "min15": AD.constant.Period.min15.value,
        "min30": AD.constant.Period.min30.value,
        "min60": AD.constant.Period.min60.value,
        "day": AD.constant.Period.day.value,
        "week": AD.constant.Period.week.value,
        "month": AD.constant.Period.month.value,
    }
    if req.period not in period_map:
        raise HTTPException(status_code=400, detail=f"Invalid period: {req.period}")

    results = []
    errors = []
    for sym in req.symbols:
        try:
            count = data_fetch_kline(sym, period_map[req.period], req.start_date, req.end_date, use_subprocess=True)
            results.append({"symbol": sym, "count": count})
        except Exception as e:
            errors.append({"symbol": sym, "error": str(e)})

    return {
        "success": len(results),
        "failed": len(errors),
        "results": results,
        "errors": errors,
    }


class ChartDataRequest(BaseModel):
    symbol: str
    start_date: str | None = None
    end_date: str | None = None
    period: str = "1D"
    adjust: str = "none"
    layers: list[dict] | None = None


@router.post("/chart-data")
def get_chart_data(req: ChartDataRequest):
    """返回 OHLCV + 指标数据（给前端 ECharts 内联渲染用）。"""
    from backend.plotting.compute import compute_indicator

    try:
        start_dt = datetime.strptime(req.start_date, "%Y-%m-%d") if req.start_date else None
        end_dt = datetime.strptime(req.end_date, "%Y-%m-%d") if req.end_date else None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")

    valid_periods = ("1min", "5min", "15min", "30min", "60min", "120min", "1D", "1W", "1M", "1Q")
    if req.period not in valid_periods:
        raise HTTPException(status_code=400, detail=f"Invalid period, supported: {valid_periods}")

    valid_adjust = ("none", "hfq", "qfq")
    if req.adjust not in valid_adjust:
        raise HTTPException(status_code=400, detail=f"Invalid adjust, supported: {valid_adjust}")

    data_dict = get_market_data(req.symbol, start_dt, end_dt, req.period, req.adjust)
    df = data_dict.get(req.symbol, pd.DataFrame())
    if df.empty:
        return {"symbol": req.symbol, "period": req.period, "adjust": req.adjust, "ohlcv": [], "indicators": []}

    df_out = df[["timestamp", "open", "high", "low", "close", "volume", "amount"]].copy()
    df_out["timestamp"] = df_out["timestamp"].astype(str)
    df_out["volume"] = df_out["volume"].astype(int)
    df_out["open"] = df_out["open"].astype(float)
    df_out["high"] = df_out["high"].astype(float)
    df_out["low"] = df_out["low"].astype(float)
    df_out["close"] = df_out["close"].astype(float)
    df_out["amount"] = df_out["amount"].astype(float)
    ohlcv = df_out.to_dict(orient="records")

    if req.layers:
        layers = [_raw_to_layerspec(raw) for raw in req.layers]
    else:
        layers = [_raw_to_layerspec(d) for d in DEFAULT_LAYERS]

    from backend.plotting.compute import enrich_for_layers

    enriched = enrich_for_layers(df, layers)
    indicators = []
    for spec in layers:
        ind = compute_indicator(enriched, spec.indicator, spec.params)
        if spec.pane is not None:
            ind.pane = spec.pane
        if spec.kind is not None:
            ind.kind = spec.kind
        if spec.color is not None:
            ind.color = spec.color
        if spec.name:
            ind.name = spec.name
        indicators.append(indicator_series_to_dict(ind))

    return {"symbol": req.symbol, "period": req.period, "adjust": req.adjust, "ohlcv": ohlcv, "indicators": indicators}

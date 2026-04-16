"""数据管理 API"""

from datetime import datetime
from typing import List

from fastapi import APIRouter, HTTPException, UploadFile, status
from pydantic import BaseModel
import pandas as pd

from backend.db import import_kline, list_symbols, query_kline

router = APIRouter(prefix="/data", tags=["data"])


class KlineImportRequest(BaseModel):
    symbol: str
    start_date: str
    end_date: str
    # CSV 格式数据或 JSON 格式数据
    data: List[dict]


class SymbolResponse(BaseModel):
    symbol: str


@router.get("/symbols", response_model=List[str])
def get_symbols():
    """获取可用标的列表"""
    return list_symbols()


@router.get("/kline")
def get_kline_data(symbol: str, start_date: str | None = None, end_date: str | None = None):
    """获取K线数据

    Args:
        symbol: 标的代码
        start_date: 开始日期 YYYY-MM-DD
        end_date: 结束日期 YYYY-MM-DD
    """
    start_dt = datetime.strptime(start_date, "%Y-%m-%d") if start_date else None
    end_dt = datetime.strptime(end_date, "%Y-%m-%d") if end_date else None

    data = query_kline(symbol, start_dt, end_dt)

    # 转换为 JSON 友好格式
    result = []
    for _, row in data.iterrows():
        result.append({
            "timestamp": row["timestamp"].isoformat(),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": int(row["volume"]),
            "amount": float(row.get("amount", 0)),
        })

    return {"symbol": symbol, "data": result}


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

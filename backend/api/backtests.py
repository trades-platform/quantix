"""回测 API"""

import json
from datetime import datetime
from decimal import Decimal
from typing import List

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from backend.db import SessionLocal, query_kline
from backend.engine import BacktestEngine
from backend.models import Backtest, Strategy, Trade

router = APIRouter(prefix="/backtests", tags=["backtests"])


class BacktestCreate(BaseModel):
    strategy_id: int
    symbol: str
    start_date: str = Field(..., description="格式: YYYY-MM-DD")
    end_date: str = Field(..., description="格式: YYYY-MM-DD")
    initial_capital: float = Field(default=1000000.0, ge=0)
    commission: float = Field(default=0.0003, ge=0, le=1)

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError("Invalid date format. Expected YYYY-MM-DD")
        return v


class BacktestResponse(BaseModel):
    id: int
    strategy_id: int
    symbol: str
    start_date: str
    end_date: str
    initial_capital: float
    commission: float
    status: str
    total_return: float | None = None
    annual_return: float | None = None
    sharpe_ratio: float | None = None
    max_drawdown: float | None = None
    win_rate: float | None = None
    created_at: datetime

    @classmethod
    def from_orm(cls, obj: Backtest) -> "BacktestResponse":
        return cls(
            id=obj.id,
            strategy_id=obj.strategy_id,
            symbol=obj.symbol,
            start_date=obj.start_date.isoformat(),
            end_date=obj.end_date.isoformat(),
            initial_capital=float(obj.initial_capital),
            commission=float(obj.commission),
            status=obj.status,
            total_return=float(obj.total_return) if obj.total_return else None,
            annual_return=float(obj.annual_return) if obj.annual_return else None,
            sharpe_ratio=float(obj.sharpe_ratio) if obj.sharpe_ratio else None,
            max_drawdown=float(obj.max_drawdown) if obj.max_drawdown else None,
            win_rate=float(obj.win_rate) if obj.win_rate else None,
            created_at=obj.created_at,
        )


class TradeResponse(BaseModel):
    id: int
    backtest_id: int
    symbol: str
    side: str
    price: float
    quantity: int
    timestamp: datetime


@router.post("", response_model=BacktestResponse, status_code=status.HTTP_201_CREATED)
def create_backtest(req: BacktestCreate):
    """创建并执行回测"""
    with SessionLocal() as db:
        # 检查策略是否存在
        strategy = db.query(Strategy).filter(Strategy.id == req.strategy_id).first()
        if not strategy:
            raise HTTPException(status_code=404, detail="策略不存在")

        # 创建回测记录
        backtest = Backtest(
            strategy_id=req.strategy_id,
            symbol=req.symbol,
            start_date=datetime.strptime(req.start_date, "%Y-%m-%d").date(),
            end_date=datetime.strptime(req.end_date, "%Y-%m-%d").date(),
            initial_capital=Decimal(str(req.initial_capital)),
            commission=Decimal(str(req.commission)),
            status="running",
        )
        db.add(backtest)
        db.commit()
        db.refresh(backtest)

        # 查询K线数据
        start_dt = datetime.strptime(req.start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(req.end_date, "%Y-%m-%d")
        kline_data = query_kline(req.symbol, start_dt, end_dt)

        if len(kline_data) == 0:
            backtest.status = "failed"
            db.commit()
            raise HTTPException(status_code=400, detail=f"无 {req.symbol} 的K线数据")

        # 执行回测
        engine = BacktestEngine(
            strategy_code=strategy.code,
            data=kline_data,
            symbol=req.symbol,
            initial_capital=req.initial_capital,
            commission=req.commission,
        )
        result = engine.run()

        # 更新回测结果
        backtest.status = result["status"]
        backtest.total_return = Decimal(str(result["metrics"]["total_return"]))
        backtest.annual_return = Decimal(str(result["metrics"]["annual_return"]))
        backtest.sharpe_ratio = Decimal(str(result["metrics"]["sharpe_ratio"]))
        backtest.max_drawdown = Decimal(str(result["metrics"]["max_drawdown"]))
        backtest.win_rate = Decimal(str(result["metrics"]["win_rate"]))
        backtest.equity_curve = json.dumps(result["equity_curve"])
        db.commit()

        # 保存交易记录
        for trade in result["trades"]:
            db_trade = Trade(
                backtest_id=backtest.id,
                symbol=trade["symbol"],
                side=trade["side"],
                price=Decimal(str(trade["price"])),
                quantity=trade["quantity"],
                timestamp=datetime.fromisoformat(trade["timestamp"]) if isinstance(trade["timestamp"], str) else datetime.utcnow(),
            )
            db.add(db_trade)
        db.commit()

        db.refresh(backtest)
        return BacktestResponse.from_orm(backtest)


@router.get("/{backtest_id}", response_model=BacktestResponse)
def get_backtest(backtest_id: int):
    """获取回测结果"""
    with SessionLocal() as db:
        backtest = db.query(Backtest).filter(Backtest.id == backtest_id).first()
        if not backtest:
            raise HTTPException(status_code=404, detail="回测不存在")
        return BacktestResponse.from_orm(backtest)


@router.get("/{backtest_id}/trades", response_model=List[TradeResponse])
def get_backtest_trades(backtest_id: int):
    """获取交易明细"""
    with SessionLocal() as db:
        backtest = db.query(Backtest).filter(Backtest.id == backtest_id).first()
        if not backtest:
            raise HTTPException(status_code=404, detail="回测不存在")

        trades = db.query(Trade).filter(Trade.backtest_id == backtest_id).order_by(Trade.timestamp).all()
        return [
            TradeResponse(
                id=t.id,
                backtest_id=t.backtest_id,
                symbol=t.symbol,
                side=t.side,
                price=float(t.price),
                quantity=t.quantity,
                timestamp=t.timestamp,
            )
            for t in trades
        ]


@router.delete("/{backtest_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_backtest(backtest_id: int):
    """删除回测结果"""
    with SessionLocal() as db:
        backtest = db.query(Backtest).filter(Backtest.id == backtest_id).first()
        if not backtest:
            raise HTTPException(status_code=404, detail="回测不存在")

        db.delete(backtest)
        db.commit()
        return None

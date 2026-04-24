"""回测 API"""

import json
from datetime import datetime
from decimal import Decimal
from typing import List

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, field_validator, model_validator

from backend.db import SessionLocal, get_display_target, get_market_data, resolve_symbol_targets
from backend.engine import BacktestEngine
from backend.models import Backtest, Strategy, Trade

router = APIRouter(prefix="/backtests", tags=["backtests"])


class BacktestCreate(BaseModel):
    strategy_id: int
    symbol: str | None = None
    symbols: list[str] | None = None
    pool_name: str | None = None
    start_date: str = Field(..., description="格式: YYYY-MM-DD")
    end_date: str = Field(..., description="格式: YYYY-MM-DD")
    initial_capital: float = Field(default=1000000.0, ge=0)
    commission: float = Field(default=0.0003, ge=0, le=1)
    period: str = Field(default="1min", description="K线周期: 1min, 5min, 15min, 30min, 60min, 120min, 1D, 1W, 1M, 1Q")
    adjust: str = Field(default="hfq", description="复权方式: none, hfq(后复权), qfq(前复权)")

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError("Invalid date format. Expected YYYY-MM-DD")
        return v

    @model_validator(mode="after")
    def validate_target(self) -> "BacktestCreate":
        provided = [
            bool(self.symbol and self.symbol.strip()),
            bool(self.symbols),
            bool(self.pool_name and self.pool_name.strip()),
        ]
        if sum(provided) != 1:
            raise ValueError("必须且只能提供 symbol、symbols 或 pool_name 其中一个")
        return self


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
    commission: float | None = None
    pnl: float | None = None


@router.post("", response_model=BacktestResponse, status_code=status.HTTP_201_CREATED)
def create_backtest(req: BacktestCreate):
    """创建并执行回测"""
    with SessionLocal() as db:
        # 检查策略是否存在
        strategy = db.query(Strategy).filter(Strategy.id == req.strategy_id).first()
        if not strategy:
            raise HTTPException(status_code=404, detail="策略不存在")

        try:
            raw_target = req.pool_name and f"@{req.pool_name}" or req.symbols or req.symbol or ""
            display_target = get_display_target(raw_target)
            resolved_symbols = resolve_symbol_targets(db, raw_target)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        # 创建回测记录
        backtest = Backtest(
            strategy_id=req.strategy_id,
            symbol=display_target,
            start_date=datetime.strptime(req.start_date, "%Y-%m-%d").date(),
            end_date=datetime.strptime(req.end_date, "%Y-%m-%d").date(),
            initial_capital=Decimal(str(req.initial_capital)),
            commission=Decimal(str(req.commission)),
            period=req.period,
            adjust=req.adjust,
            status="running",
        )
        db.add(backtest)
        db.commit()
        db.refresh(backtest)

        # 查询行情数据（含复权 + 重采样）
        start_dt = datetime.strptime(req.start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(req.end_date, "%Y-%m-%d")
        data_dict = get_market_data(
            symbols=resolved_symbols,
            start_date=start_dt,
            end_date=end_dt,
            period=req.period,
            adjust=req.adjust,
        )

        missing_symbols = [symbol for symbol in resolved_symbols if symbol not in data_dict or data_dict[symbol].empty]
        if missing_symbols:
            backtest.status = "failed"
            db.commit()
            if len(missing_symbols) == 1:
                raise HTTPException(status_code=400, detail=f"无 {missing_symbols[0]} 的K线数据")
            raise HTTPException(status_code=400, detail=f"以下标的缺少K线数据: {', '.join(missing_symbols)}")

        engine_input = (
            data_dict[resolved_symbols[0]]
            if len(resolved_symbols) == 1
            else {symbol: data_dict[symbol] for symbol in resolved_symbols}
        )

        # 执行回测
        engine = BacktestEngine(
            strategy_code=strategy.code,
            data=engine_input,
            symbol=resolved_symbols if len(resolved_symbols) > 1 else resolved_symbols[0],
            initial_capital=req.initial_capital,
            commission=req.commission,
            period=req.period,
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
                commission=Decimal(str(trade.get("commission", 0))) if trade.get("commission") is not None else None,
                pnl=Decimal(str(trade.get("pnl", 0))) if trade.get("pnl") is not None else None,
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
                commission=float(t.commission) if t.commission else None,
                pnl=float(t.pnl) if t.pnl else None,
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

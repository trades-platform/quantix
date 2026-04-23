"""回测结果相关的 SQLAlchemy 模型"""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Column, Date, DateTime, Numeric, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Backtest(Base):
    """回测结果模型"""

    __tablename__ = "backtests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=False)
    symbol = Column(String(20), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    initial_capital = Column(Numeric(15, 2), nullable=False)
    commission = Column(Numeric(8, 4), nullable=False)
    slippage = Column(Numeric(10, 4), nullable=True)
    period = Column(String(10), nullable=True)
    adjust = Column(String(10), nullable=True)
    status = Column(String(20), nullable=False, default="pending")
    total_return = Column(Numeric(10, 4), nullable=True)
    annual_return = Column(Numeric(10, 4), nullable=True)
    sharpe_ratio = Column(Numeric(10, 4), nullable=True)
    max_drawdown = Column(Numeric(10, 4), nullable=True)
    win_rate = Column(Numeric(10, 4), nullable=True)
    equity_curve = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    trades = relationship("Trade", back_populates="backtest", cascade="all, delete-orphan")


class Trade(Base):
    """交易明细模型"""

    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    backtest_id = Column(Integer, ForeignKey("backtests.id"), nullable=False)
    symbol = Column(String(20), nullable=False)
    side = Column(String(10), nullable=False)
    price = Column(Numeric(15, 2), nullable=False)
    quantity = Column(Integer, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    commission = Column(Numeric(15, 4), nullable=True)
    pnl = Column(Numeric(15, 4), nullable=True)

    backtest = relationship("Backtest", back_populates="trades")

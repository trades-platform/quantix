"""已导入标的元信息模型"""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String

from backend.models.backtest import Base


class Symbol(Base):
    """已导入标的元信息"""

    __tablename__ = "symbols"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, unique=True)
    name = Column(String(50), nullable=True)
    data_type = Column(String(10), nullable=True)  # stock / etf
    earliest_timestamp = Column(DateTime, nullable=True)
    latest_timestamp = Column(DateTime, nullable=True)
    row_count = Column(Integer, default=0)
    period = Column(String(10), default="min1")
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

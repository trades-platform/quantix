"""标的池模型"""

import json
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text

from backend.models.backtest import Base


class SymbolPool(Base):
    """可复用的标的代码集合"""

    __tablename__ = "symbol_pools"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), nullable=False, unique=True)
    description = Column(String(255), nullable=True)
    symbols_json = Column(Text, nullable=False, default="[]")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    @property
    def symbols(self) -> list[str]:
        return json.loads(self.symbols_json or "[]")

    @symbols.setter
    def symbols(self, value: list[str]) -> None:
        self.symbols_json = json.dumps(value, ensure_ascii=False)

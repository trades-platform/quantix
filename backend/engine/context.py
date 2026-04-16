"""回测上下文，提供给策略使用"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Bar:
    """单根K线数据"""

    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    symbol: str


@dataclass
class Context:
    """策略回测上下文"""

    symbol: str
    initial_capital: float
    commission: float
    current_bar: Bar | None = None
    bar_index: int = 0
    datetime: str = ""
    cash: float = 0.0
    portfolio_value: float = 0.0
    positions: dict[str, int] = field(default_factory=dict)
    orders: list = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.cash = self.initial_capital
        self.portfolio_value = self.initial_capital

    def update(self, bar: Bar):
        """更新当前K线数据"""
        self.current_bar = bar
        self.bar_index += 1
        self.datetime = bar.timestamp

    def set_attr(self, key: str, value: Any):
        """设置策略自定义属性"""
        self.attributes[key] = value

    def get_attr(self, key: str, default: Any = None) -> Any:
        """获取策略自定义属性"""
        return self.attributes.get(key, default)

    def order(self, symbol: str, quantity: int):
        """下单"""
        self.orders.append({"symbol": symbol, "quantity": quantity, "timestamp": self.datetime})

    def buy(self, symbol: str, quantity: int):
        """买入"""
        self.order(symbol, abs(quantity))

    def sell(self, symbol: str, quantity: int):
        """卖出"""
        self.order(symbol, -abs(quantity))

    def get_position(self, symbol: str) -> int:
        """获取持仓数量"""
        return self.positions.get(symbol, 0)

    def current_price(self, symbol: str) -> float:
        """获取当前价格"""
        if self.current_bar and self.current_bar.symbol == symbol:
            return self.current_bar.close
        return 0.0

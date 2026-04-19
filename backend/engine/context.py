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
    raw_open: float = 0.0
    raw_high: float = 0.0
    raw_low: float = 0.0
    raw_close: float = 0.0


@dataclass
class Context:
    """策略回测上下文"""

    symbol: str
    initial_capital: float
    commission: float
    symbols: list[str] = field(default_factory=list)
    current_bars: dict[str, Bar] = field(default_factory=dict)
    bar_index: int = 0
    datetime: str = ""
    cash: float = 0.0
    portfolio_value: float = 0.0
    positions: dict[str, int] = field(default_factory=dict)
    orders: list = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)
    indicators_map: dict = field(default_factory=dict)

    def __post_init__(self):
        self.cash = self.initial_capital
        self.portfolio_value = self.initial_capital
        # 如果 symbols 为空但 symbol 有值，设置 symbols = [symbol]
        if not self.symbols and self.symbol:
            self.symbols = [self.symbol]

    @property
    def current_bar(self) -> Bar | None:
        """获取当前K线 (单标的后向兼容)"""
        if self.current_bars and self.symbols:
            return self.current_bars.get(self.symbols[0])
        return None

    @current_bar.setter
    def current_bar(self, value: Bar | None):
        """设置当前K线"""
        if value is not None:
            self.current_bars[value.symbol] = value

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
        if symbol in self.current_bars:
            return self.current_bars[symbol].close
        if self.current_bar and self.current_bar.symbol == symbol:
            return self.current_bar.close
        return 0.0

    @property
    def indicators(self):
        """获取第一个标的的技术指标"""
        if self.symbols:
            return self.indicators_map.get(self.symbols[0])
        return None

    def indicators_for(self, symbol: str):
        """获取指定标的的技术指标"""
        return self.indicators_map.get(symbol)

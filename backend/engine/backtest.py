"""回测引擎核心模块"""

import pandas as pd

from backend.engine.context import Bar, Context
from backend.engine.executor import StrategyExecutor
from backend.engine.metrics import calculate_metrics


class Portfolio:
    """投资组合，管理资金和持仓"""

    def __init__(self, initial_capital: float, commission: float):
        self.initial_capital = initial_capital
        self.commission = commission
        self.cash = initial_capital
        self.positions: dict[str, int] = {}
        self.trades = []
        self.equity_curve = [initial_capital]

    def execute_order(self, order: dict, price: float) -> bool:
        """执行订单"""
        symbol = order["symbol"]
        quantity = order["quantity"]

        if quantity > 0:  # 买入
            required = price * quantity * (1 + self.commission)
            if required > self.cash:
                return False  # 资金不足

            self.cash -= required
            self.positions[symbol] = self.positions.get(symbol, 0) + quantity
            self.trades.append({
                "symbol": symbol,
                "side": "buy",
                "price": price,
                "quantity": quantity,
                "timestamp": order.get("timestamp"),
            })
        else:  # 卖出
            quantity = abs(quantity)
            if self.positions.get(symbol, 0) < quantity:
                return False  # 持仓不足

            proceeds = price * quantity * (1 - self.commission)
            self.cash += proceeds
            self.positions[symbol] = self.positions.get(symbol, 0) - quantity
            if self.positions[symbol] == 0:
                del self.positions[symbol]

            self.trades.append({
                "symbol": symbol,
                "side": "sell",
                "price": price,
                "quantity": quantity,
                "timestamp": order.get("timestamp"),
            })

        return True

    def update_value(self, prices: dict[str, float]):
        """更新组合价值"""
        position_value = sum(qty * prices.get(symbol, 0) for symbol, qty in self.positions.items())
        self.equity_curve.append(self.cash + position_value)


class BacktestEngine:
    """回测引擎"""

    def __init__(
        self,
        strategy_code: str,
        data: pd.DataFrame,
        symbol: str,
        initial_capital: float = 1000000.0,
        commission: float = 0.0003,
    ):
        self.strategy_code = strategy_code
        self.data = data
        self.symbol = symbol
        self.initial_capital = initial_capital
        self.commission = commission

    def run(self) -> dict:
        """运行回测

        Returns:
            回测结果字典
        """
        if len(self.data) == 0:
            return self._empty_result()

        # 创建策略执行器
        executor = StrategyExecutor(self.strategy_code)
        executor.load()

        # 创建上下文
        context = Context(
            symbol=self.symbol,
            initial_capital=self.initial_capital,
            commission=self.commission,
        )

        # 创建投资组合
        portfolio = Portfolio(self.initial_capital, self.commission)

        # 初始化策略
        executor.initialize(context)

        # 逐根K线回放
        for _, row in self.data.iterrows():
            bar = Bar(
                timestamp=str(row["timestamp"]),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"]),
                symbol=self.symbol,
            )

            # 更新上下文
            context.update(bar)

            # 执行策略
            orders = executor.handle_bar(context)

            # 执行订单
            for order in orders:
                portfolio.execute_order(order, bar.close)

            # 更新持仓到上下文
            context.positions = portfolio.positions.copy()
            context.cash = portfolio.cash
            context.portfolio_value = portfolio.equity_curve[-1]

            # 更新组合价值
            portfolio.update_value({self.symbol: bar.close})

        # 计算性能指标
        metrics = calculate_metrics(portfolio.equity_curve, portfolio.trades)

        return {
            "status": "completed",
            "metrics": metrics,
            "equity_curve": portfolio.equity_curve,
            "trades": portfolio.trades,
            "final_value": portfolio.equity_curve[-1] if portfolio.equity_curve else self.initial_capital,
        }

    def _empty_result(self) -> dict:
        """返回空结果"""
        return {
            "status": "failed",
            "error": "无可用数据",
            "metrics": {
                "total_return": 0.0,
                "annual_return": 0.0,
                "sharpe_ratio": 0.0,
                "max_drawdown": 0.0,
                "win_rate": 0.0,
            },
            "equity_curve": [],
            "trades": [],
            "final_value": self.initial_capital,
        }

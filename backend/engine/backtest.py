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
        self._avg_cost: dict[str, float] = {}  # 持仓平均成本

    def execute_order(self, order: dict, price: float) -> bool:
        """执行订单"""
        symbol = order["symbol"]
        quantity = order["quantity"]

        if quantity > 0:  # 买入
            required = price * quantity * (1 + self.commission)
            if required > self.cash:
                return False  # 资金不足

            commission_cost = price * quantity * self.commission
            self.cash -= required
            self.positions[symbol] = self.positions.get(symbol, 0) + quantity

            # 更新平均成本
            current_cost = self._avg_cost.get(symbol, 0.0)
            current_qty = self.positions[symbol] - quantity
            new_qty = quantity
            if current_qty > 0:
                self._avg_cost[symbol] = (current_cost * current_qty + price * new_qty) / (current_qty + new_qty)
            else:
                self._avg_cost[symbol] = price

            self.trades.append({
                "symbol": symbol,
                "side": "buy",
                "price": price,
                "quantity": quantity,
                "commission": commission_cost,
                "pnl": 0.0,
                "timestamp": order.get("timestamp"),
            })
        else:  # 卖出
            quantity = abs(quantity)
            if self.positions.get(symbol, 0) < quantity:
                return False  # 持仓不足

            # 计算盈亏（必须在更新持仓之前取 avg_cost）
            avg_cost = self._avg_cost.get(symbol, 0.0)
            pnl = (price - avg_cost) * quantity

            commission_cost = price * quantity * self.commission
            proceeds = price * quantity * (1 - self.commission)
            self.cash += proceeds
            self.positions[symbol] = self.positions.get(symbol, 0) - quantity
            if self.positions[symbol] == 0:
                del self.positions[symbol]
                if symbol in self._avg_cost:
                    del self._avg_cost[symbol]

            self.trades.append({
                "symbol": symbol,
                "side": "sell",
                "price": price,
                "quantity": quantity,
                "commission": commission_cost,
                "pnl": pnl,
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
        data: pd.DataFrame | dict[str, pd.DataFrame],
        symbol: str | list[str],
        initial_capital: float = 1000000.0,
        commission: float = 0.0003,
        period: str = "1min",
        params: dict | None = None,
    ):
        self.strategy_code = strategy_code
        # 向后兼容：如果传入单个字符串，包装成列表
        if isinstance(symbol, str):
            self.symbols = [symbol]
        else:
            self.symbols = symbol

        # 向后兼容：如果传入单个 DataFrame，包装成字典
        if isinstance(data, pd.DataFrame):
            self.data = {self.symbols[0]: data}
        else:
            self.data = data

        self.symbol = self.symbols[0]  # 保留第一个标的作为默认值
        self.initial_capital = initial_capital
        self.commission = commission
        self.period = period
        self.params = params or {}

    def run(self) -> dict:
        """运行回测

        Returns:
            回测结果字典
        """
        if not self.data:
            return self._empty_result()

        # 创建策略执行器
        executor = StrategyExecutor(self.strategy_code)
        executor.load()

        # 重采样数据 (如果需要)
        from backend.engine.resample import resample_kline
        from backend.engine.indicators import SymbolIndicators

        resampled_data = {}
        for symbol, df in self.data.items():
            if len(df) == 0:
                continue
            if self.period != "1min":
                resampled_data[symbol] = resample_kline(df, self.period)
            else:
                resampled_data[symbol] = df

        if not resampled_data:
            return self._empty_result()

        # 创建上下文
        context = Context(
            symbol=self.symbol,
            initial_capital=self.initial_capital,
            commission=self.commission,
            symbols=self.symbols,
            params=self.params,
        )

        # 创建投资组合
        portfolio = Portfolio(self.initial_capital, self.commission)

        # 初始化策略
        executor.initialize(context)

        # 预处理：确保 timestamp 列为 datetime 类型并排序
        for symbol in resampled_data:
            df = resampled_data[symbol]
            if not pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
                df["timestamp"] = pd.to_datetime(df["timestamp"])
            resampled_data[symbol] = df.sort_values("timestamp").reset_index(drop=True)

        # 收集所有时间戳并排序（用 datetime 而非字符串）
        all_timestamps = set()
        for df in resampled_data.values():
            all_timestamps.update(df["timestamp"].tolist())
        sorted_timestamps = sorted(all_timestamps)

        # 为每个标的建立行索引追踪
        row_indices = {symbol: 0 for symbol in resampled_data}

        # 逐根K线回放
        for ts in sorted_timestamps:
            # 为每个标的构建当前 Bar
            current_bars = {}
            for symbol, df in resampled_data.items():
                idx = row_indices[symbol]
                if idx < len(df) and df["timestamp"].iloc[idx] == ts:
                    row = df.iloc[idx]
                    bar = Bar(
                        timestamp=str(row["timestamp"]),
                        open=float(row["open"]),
                        high=float(row["high"]),
                        low=float(row["low"]),
                        close=float(row["close"]),
                        volume=float(row["volume"]),
                        symbol=symbol,
                    )
                    current_bars[symbol] = bar
                    row_indices[symbol] = idx + 1

            if not current_bars:
                continue

            # 更新上下文
            context.current_bars = current_bars
            context.bar_index += 1
            context.datetime = str(ts)

            # 更新每个标的的技术指标（使用行索引切片，O(1)）
            for symbol in current_bars:
                idx = row_indices[symbol]
                history = resampled_data[symbol].iloc[:idx]
                if len(history) > 0:
                    context.indicators_map[symbol] = SymbolIndicators(history)

            # 执行策略
            orders = executor.handle_bar(context)

            # 执行订单
            for order in orders:
                sym = order.get("symbol")
                if sym in current_bars:
                    portfolio.execute_order(order, current_bars[sym].close)

            # 更新持仓到上下文
            context.positions = portfolio.positions.copy()
            context.cash = portfolio.cash
            context.portfolio_value = portfolio.equity_curve[-1]

            # 更新组合价值
            prices = {sym: bar.close for sym, bar in current_bars.items()}
            portfolio.update_value(prices)

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

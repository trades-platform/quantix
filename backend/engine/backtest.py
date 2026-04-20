"""回测引擎核心模块"""

import pandas as pd

from backend.engine.context import Bar, Context


# K线周期 → 每年 bar 数量（A股：252 交易日，每天 4 小时 = 240 分钟）
_BARS_PER_YEAR: dict[str, int] = {
    "1min": 252 * 240,
    "5min": 252 * 48,
    "15min": 252 * 16,
    "30min": 252 * 8,
    "60min": 252 * 4,
    "120min": 252 * 2,
    "1D": 252,
    "1W": 52,
    "1M": 12,
    "1Q": 4,
}


def _bars_per_year(period: str) -> int:
    """根据 K 线周期返回每年的 bar 数量"""
    return _BARS_PER_YEAR.get(period, 252)
from backend.engine.executor import StrategyExecutor
from backend.engine.metrics import calculate_metrics


class Portfolio:
    """投资组合，管理资金和持仓"""

    def __init__(self, initial_capital: float, commission: float, slippage: float = 0.001):
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage
        self.cash = initial_capital
        self.positions: dict[str, int] = {}
        self.trades = []
        self.equity_curve = [initial_capital]
        self._avg_cost: dict[str, float] = {}  # 持仓平均成本

    def execute_order(self, order: dict, price: float) -> bool:
        """执行订单，含滑点

        Args:
            order: 订单字典，包含 symbol, quantity, timestamp
            price: 基础执行价格（开盘价），滑点在此基础上调整

        Returns:
            是否执行成功
        """
        symbol = order["symbol"]
        quantity = order["quantity"]

        if quantity > 0:  # 买入
            # 滑点：买入价上浮
            exec_price = price * (1 + self.slippage)
            required = exec_price * quantity * (1 + self.commission)
            if required > self.cash:
                return False  # 资金不足

            commission_cost = exec_price * quantity * self.commission
            self.cash -= required
            self.positions[symbol] = self.positions.get(symbol, 0) + quantity

            # 更新平均成本
            current_cost = self._avg_cost.get(symbol, 0.0)
            current_qty = self.positions[symbol] - quantity
            new_qty = quantity
            if current_qty > 0:
                self._avg_cost[symbol] = (current_cost * current_qty + exec_price * new_qty) / (current_qty + new_qty)
            else:
                self._avg_cost[symbol] = exec_price

            self.trades.append({
                "symbol": symbol,
                "side": "buy",
                "price": exec_price,
                "quantity": quantity,
                "commission": commission_cost,
                "pnl": -commission_cost,
                "timestamp": order.get("timestamp"),
            })
        else:  # 卖出
            # 滑点：卖出价下浮
            exec_price = price * (1 - self.slippage)
            quantity = abs(quantity)
            if self.positions.get(symbol, 0) < quantity:
                return False  # 持仓不足

            # 计算盈亏（必须在更新持仓之前取 avg_cost）
            avg_cost = self._avg_cost.get(symbol, 0.0)
            gross_pnl = (exec_price - avg_cost) * quantity
            commission_cost = exec_price * quantity * self.commission
            net_pnl = gross_pnl - commission_cost

            proceeds = exec_price * quantity * (1 - self.commission)
            self.cash += proceeds
            self.positions[symbol] = self.positions.get(symbol, 0) - quantity
            if self.positions[symbol] == 0:
                del self.positions[symbol]
                if symbol in self._avg_cost:
                    del self._avg_cost[symbol]

            self.trades.append({
                "symbol": symbol,
                "side": "sell",
                "price": exec_price,
                "quantity": quantity,
                "commission": commission_cost,
                "pnl": net_pnl,
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
        slippage: float = 0.001,
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
        self.slippage = slippage
        self.period = period
        self.params = params or {}

    def run(self) -> dict:
        """运行回测

        执行模型：信号在 bar N 生成，订单在 bar N+1 开盘价执行（含滑点）。

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

        # 创建投资组合（含滑点参数）
        portfolio = Portfolio(self.initial_capital, self.commission, self.slippage)

        # 初始化策略
        executor.initialize(context)

        # 预处理：确保 timestamp 列为 datetime 类型并排序
        for symbol in resampled_data:
            df = resampled_data[symbol]
            if not pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
                df["timestamp"] = pd.to_datetime(df["timestamp"])
            resampled_data[symbol] = df.sort_values("timestamp").reset_index(drop=True)

        # 收集所有时间戳并排序
        all_timestamps = set()
        for df in resampled_data.values():
            all_timestamps.update(df["timestamp"].tolist())
        sorted_timestamps = sorted(all_timestamps)

        # 为每个标的建立行索引追踪
        row_indices = {symbol: 0 for symbol in resampled_data}

        # 为每个标的创建持久的指标计算器（避免每轮重建）
        indicator_objects: dict[str, SymbolIndicators] = {}
        for symbol, df in resampled_data.items():
            indicator_objects[symbol] = SymbolIndicators(df)

        # 待执行订单队列（上一根 bar 生成的信号，在当前 bar 开盘执行）
        pending_orders: list[dict] = []

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

            # --- 步骤 1：在当前 bar 开盘价执行上一根 bar 的挂单 ---
            for order in pending_orders:
                sym = order.get("symbol")
                if sym in current_bars:
                    portfolio.execute_order(order, current_bars[sym].open)
                # 每笔订单执行后立即同步持仓到上下文
                context.positions = portfolio.positions.copy()
                context.cash = portfolio.cash
            pending_orders = []

            # --- 步骤 2：更新技术指标（增量，仅更新当前行索引）---
            for symbol in current_bars:
                idx = row_indices[symbol]
                indicator_objects[symbol].set_current_idx(idx)
                context.indicators_map[symbol] = indicator_objects[symbol]

            # --- 步骤 3：执行策略，生成新信号 ---
            orders = executor.handle_bar(context)

            # --- 步骤 4：新订单挂起，下一根 bar 开盘执行 ---
            pending_orders = orders

            # --- 步骤 5：更新组合价值 ---
            prices = {sym: bar.close for sym, bar in current_bars.items()}
            portfolio.update_value(prices)
            context.portfolio_value = portfolio.equity_curve[-1]

        # 计算性能指标
        bars_per_year = _bars_per_year(self.period)
        metrics = calculate_metrics(portfolio.equity_curve, portfolio.trades, bars_per_year=bars_per_year)

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

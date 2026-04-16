"""性能指标计算模块"""

import numpy as np


def calculate_metrics(equity_curve: list[float], trades: list, risk_free_rate: float = 0.03) -> dict:
    """计算回测性能指标

    Args:
        equity_curve: 资金曲线列表
        trades: 交易记录列表，每个交易包含 side, price, quantity
        risk_free_rate: 无风险利率（年化）

    Returns:
        性能指标字典
    """
    if not equity_curve:
        return {
            "total_return": 0.0,
            "annual_return": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0,
            "win_rate": 0.0,
        }

    equity = np.array(equity_curve)
    initial = equity[0]
    final = equity[-1]

    # 总收益率
    total_return = (final - initial) / initial if initial > 0 else 0.0

    # 年化收益率（假设252个交易日）
    n = len(equity_curve)
    annual_return = (1 + total_return) ** (252 / n) - 1 if n > 0 else 0.0

    # 夏普比率
    if n > 1:
        returns = np.diff(equity) / equity[:-1]
        excess_returns = returns - risk_free_rate / 252
        sharpe_ratio = np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252) if np.std(excess_returns) > 0 else 0.0
    else:
        sharpe_ratio = 0.0

    # 最大回撤
    cumulative = np.maximum.accumulate(equity)
    drawdown = (equity - cumulative) / cumulative
    max_drawdown = np.min(drawdown) if len(drawdown) > 0 else 0.0

    # 胜率
    win_rate = 0.0
    if trades:
        round_trips = _group_round_trips(trades)
        if round_trips:
            winning = sum(1 for t in round_trips if t.get("profit", 0) > 0)
            win_rate = winning / len(round_trips)

    return {
        "total_return": float(total_return),
        "annual_return": float(annual_return),
        "sharpe_ratio": float(sharpe_ratio),
        "max_drawdown": float(max_drawdown),
        "win_rate": float(win_rate),
    }


def _group_round_trips(trades: list) -> list:
    """将交易配对为完整的往返交易"""
    positions = {}
    round_trips = []

    for trade in trades:
        symbol = trade["symbol"]
        side = trade["side"]
        quantity = trade["quantity"]
        price = trade["price"]

        if symbol not in positions:
            positions[symbol] = {"quantity": 0, "cost": 0.0}

        pos = positions[symbol]

        if side == "buy":
            pos["quantity"] += quantity
            pos["cost"] += price * quantity
        elif side == "sell":
            if pos["quantity"] >= quantity:
                # 平仓
                avg_cost = pos["cost"] / pos["quantity"] if pos["quantity"] > 0 else 0
                profit = (price - avg_cost) * quantity
                round_trips.append({"symbol": symbol, "profit": profit})
                pos["quantity"] -= quantity
                pos["cost"] -= avg_cost * quantity
            else:
                # 卖空（暂不处理）
                pass

    return round_trips

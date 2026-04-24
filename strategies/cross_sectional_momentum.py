"""截面动量策略 (Cross-Sectional Momentum)

在行业/板块ETF池中，每期买入近期表现最好的前 N 个标的，等权配置。

适用标的：多个行业或宽基ETF，如 510300.SH,510500.SH,512000.SH,512690.SH,515220.SH

用法:
  quantix backtest run-file strategies/cross_sectional_momentum.py 510300.SH,510500.SH,512000.SH 2020-01-01 2026-04-24 --period 1D --adjust hfq
  quantix backtest run-file strategies/cross_sectional_momentum.py 510300.SH,510500.SH,512000.SH 2020-01-01 2026-04-24 --period 1D --adjust hfq --params '{"lookback":60,"top_n":2,"rebalance_period":20}'
"""


def initialize(context):
    context.lookback = context.params.get("lookback", 60)
    context.top_n = context.params.get("top_n", 3)
    context.rebalance_period = context.params.get("rebalance_period", 20)


def handle_bar(context):
    if context.bar_index % context.rebalance_period != 0:
        return

    returns = []
    for sym in context.symbols:
        ind = context.indicators_for(sym)
        if ind is None:
            continue
        hist = ind.history("close", context.lookback + 1)
        if len(hist) < context.lookback + 1:
            continue
        ret = (hist[-1] - hist[0]) / hist[0]
        returns.append((sym, ret))

    if not returns:
        return

    returns.sort(key=lambda x: x[1], reverse=True)
    top_symbols = {sym for sym, _ in returns[: context.top_n]}

    # 计算目标等权数量
    cash_per_symbol = context.portfolio_value * 0.9 / len(top_symbols)

    # 先卖出不在 top_n 中的持仓，以及目标持仓中超仓的部分
    for sym in context.symbols:
        pos = context.get_position(sym)
        if pos == 0:
            continue
        price = context.current_price(sym)
        if price <= 0:
            continue
        if sym not in top_symbols:
            context.sell(sym, pos)
        else:
            target_qty = int(cash_per_symbol / price / 100) * 100
            if pos > target_qty:
                context.sell(sym, pos - target_qty)

    # 再买入目标持仓中欠仓的部分
    for sym in top_symbols:
        price = context.current_price(sym)
        if price <= 0:
            continue
        target_qty = int(cash_per_symbol / price / 100) * 100
        current_pos = context.get_position(sym)
        if target_qty > current_pos:
            context.buy(sym, target_qty - current_pos)

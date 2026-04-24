"""风险调整动量策略 (Risk-Adjusted Momentum)

以夏普比率的简化版（收益率/波动率）对标的池进行排序，
每期买入风险调整后动量得分最高的前 N 个标的，等权配置。

适用标的：多个ETF组合，如 510300.SH,510500.SH,512000.SH,159915.SZ,518880.SH

用法:
  quantix backtest run-file strategies/risk_adjusted_momentum.py 510300.SH,510500.SH,512000.SH 2020-01-01 2026-04-24 --period 1D --adjust hfq
  quantix backtest run-file strategies/risk_adjusted_momentum.py 510300.SH,510500.SH,512000.SH 2020-01-01 2026-04-24 --period 1D --adjust hfq --params '{"lookback":60,"top_n":2,"rebalance_period":20}'
"""


def initialize(context):
    context.lookback = context.params.get("lookback", 60)
    context.top_n = context.params.get("top_n", 3)
    context.rebalance_period = context.params.get("rebalance_period", 20)


def handle_bar(context):
    if context.bar_index % context.rebalance_period != 0:
        return

    scores = []
    for sym in context.symbols:
        ind = context.indicators_for(sym)
        if ind is None:
            continue
        hist = ind.history("close", context.lookback + 1)
        if len(hist) < context.lookback + 1:
            continue
        ret = (hist[-1] - hist[0]) / hist[0]
        std = ind.std(context.lookback)
        if std == 0:
            continue
        score = ret / std
        scores.append((sym, score))

    if not scores:
        return

    scores.sort(key=lambda x: x[1], reverse=True)
    top_symbols = {sym for sym, _ in scores[: context.top_n]}

    cash_per_symbol = context.portfolio_value * 0.9 / len(top_symbols)

    # 先卖出非目标持仓及超仓部分
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

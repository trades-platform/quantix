"""双动量策略 (Dual Momentum)

结合相对动量与绝对动量进行择时：
- 相对动量：在标的池中选出近期表现最好的标的
- 绝对动量：若最佳标的近期收益为正则买入，否则空仓

适用标的：多个宽基ETF组合，如 510300.SH,510500.SH,510050.SH,159915.SZ

用法:
  quantix backtest run-file strategies/dual_momentum.py 510300.SH,510500.SH,510050.SH 2020-01-01 2026-04-24 --period 1D --adjust hfq
  quantix backtest run-file strategies/dual_momentum.py 510300.SH,510500.SH,510050.SH 2020-01-01 2026-04-24 --period 1D --adjust hfq --params '{"lookback":60,"rebalance_period":20}'
"""


def initialize(context):
    context.lookback = context.params.get("lookback", 60)
    context.rebalance_period = context.params.get("rebalance_period", 20)


def handle_bar(context):
    if context.bar_index % context.rebalance_period != 0:
        return

    best_sym = None
    best_return = -float("inf")

    for sym in context.symbols:
        ind = context.indicators_for(sym)
        if ind is None:
            continue
        hist = ind.history("close", context.lookback + 1)
        if len(hist) < context.lookback + 1:
            continue
        ret = (hist[-1] - hist[0]) / hist[0]
        if ret > best_return:
            best_return = ret
            best_sym = sym

    if best_sym is None:
        return

    # 清仓所有非最佳标的
    for sym in context.symbols:
        pos = context.get_position(sym)
        if pos > 0 and sym != best_sym:
            context.sell(sym, pos)

    # 绝对动量过滤：仅当最佳标的收益为正才买入
    if best_return > 0:
        price = context.current_price(best_sym)
        if price <= 0:
            return
        current_pos = context.get_position(best_sym)
        if current_pos == 0:
            qty = int(context.cash * 0.9 / price / 100) * 100
            if qty > 0:
                context.buy(best_sym, qty)
    else:
        pos = context.get_position(best_sym)
        if pos > 0:
            context.sell(best_sym, pos)

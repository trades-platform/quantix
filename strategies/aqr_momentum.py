"""AQR动量因子策略

参考 AQR 经典动量因子构建方法：
- 形成期：过去 12 个月（排除最近 1 个月，规避短期反转效应）
- 每期按形成期收益率排序，做多排名靠前的标的
- 由于回测引擎暂不支持做空，仅保留多头端：空仓排名靠后的标的

适用标的：多个宽基/行业ETF组合，如 510300.SH,510500.SH,159915.SZ,518880.SH

用法:
  quantix backtest run-file strategies/aqr_momentum.py 510300.SH,510500.SH,159915.SZ 2020-01-01 2026-04-24 --period 1D --adjust hfq
  quantix backtest run-file strategies/aqr_momentum.py 510300.SH,510500.SH,159915.SZ 2020-01-01 2026-04-24 --period 1D --adjust hfq --params '{"formation_period":240,"skip_period":20,"top_n":2,"rebalance_period":20}'
"""


def initialize(context):
    context.formation_period = context.params.get("formation_period", 240)
    context.skip_period = context.params.get("skip_period", 20)
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
        total_needed = context.formation_period + context.skip_period + 1
        hist = ind.history("close", total_needed)
        if len(hist) < total_needed:
            continue
        # 跳过最近 skip_period，计算 formation_period 收益率
        past_price = hist[-(context.skip_period + 1)]
        earlier_price = hist[0]
        if earlier_price == 0:
            continue
        ret = (past_price - earlier_price) / earlier_price
        returns.append((sym, ret))

    if not returns:
        return

    returns.sort(key=lambda x: x[1], reverse=True)
    top_symbols = {sym for sym, _ in returns[: context.top_n]}

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

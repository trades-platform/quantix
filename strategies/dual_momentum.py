"""双动量策略 (Dual Momentum)

相对动量：选出过去 N 日涨幅最大的标的
绝对动量：仅在该标的涨幅为正时持有，否则空仓

用法:
  quantix backtest run-file strategies/dual_momentum.py "159949.SZ,513100.SH" 2020-01-01 2026-05-06 --period 1D --adjust hfq
  quantix backtest run-file strategies/dual_momentum.py "159949.SZ,513100.SH" 2020-01-01 2026-05-06 --period 1D --adjust hfq --params '{"lookback":120}'
"""


def initialize(context):
    context.lookback = context.params.get("lookback", 250)
    context.last_price = {}


def _price(context, sym):
    """获取最新已知价格（解决跨市场交易日不同导致 current_price 返回 0 的问题）"""
    p = context.current_price(sym)
    if p > 0:
        context.last_price[sym] = p
    return context.last_price.get(sym, 0.0)


def handle_bar(context):
    lookback = context.lookback
    ind_map = context.indicators_map
    if not ind_map:
        return

    # 计算每个标的的 N 日收益率
    returns = {}
    for sym in context.symbols:
        ind = ind_map.get(sym)
        if ind is None:
            continue
        history = ind._visible
        if history is None or len(history) < lookback + 1:
            continue
        past_price = history["close"].iloc[-(lookback + 1)]
        cur_price = _price(context, sym)
        if past_price > 0 and cur_price > 0:
            returns[sym] = (cur_price - past_price) / past_price

    if not returns:
        return

    # 相对动量：选收益率最高的标的
    best_sym = max(returns, key=returns.get)

    # 绝对动量：仅当最优标的收益为正时持有
    hold = returns[best_sym] > 0

    # 调仓：先估算卖出回笼资金，再用总资金计算买入量
    estimated_cash = context.cash
    for sym in context.symbols:
        pos = context.get_position(sym)
        if pos > 0 and sym != best_sym:
            estimated_cash += pos * _price(context, sym)

    # 先卖后买，确保卖出资金在买入前到账
    for sym in context.symbols:
        if sym != best_sym and context.get_position(sym) > 0:
            context.sell(sym, context.get_position(sym))

    if hold:
        pos = context.get_position(best_sym)
        if pos == 0:
            price = _price(context, best_sym)
            if price > 0:
                qty = int(estimated_cash * 0.99 / price / 100) * 100
                if qty > 0:
                    context.buy(best_sym, qty)

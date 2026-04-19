"""双均线交叉策略

用法:
  quantix backtest run-file strategies/dual_ma.py 588000.SH 2025-01-01 2026-04-18 --period 1D --adjust hfq
  quantix backtest run-file strategies/dual_ma.py 588000.SH 2025-01-01 2026-04-18 --period 1D --adjust hfq --params '{"short_period":10,"long_period":30}'
"""


def initialize(context):
    context.short_period = context.params.get("short_period", 5)
    context.long_period = context.params.get("long_period", 20)
    context.bought = False


def handle_bar(context):
    ind = context.indicators
    if ind is None:
        return

    short_ma = ind.ma(context.short_period)
    long_ma = ind.ma(context.long_period)

    # 均线未计算完成
    if short_ma == 0.0 or long_ma == 0.0:
        return

    pos = context.get_position(context.symbol)

    if not context.bought and short_ma > long_ma:
        # 用 90% 资金买入
        price = context.current_price(context.symbol)
        if price > 0:
            qty = int(context.cash * 0.9 / price / 100) * 100
            if qty > 0:
                context.buy(context.symbol, qty)
                context.bought = True

    elif context.bought and short_ma < long_ma and pos > 0:
        context.sell(context.symbol, pos)
        context.bought = False

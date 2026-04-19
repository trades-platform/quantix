"""均线突破策略

价格突破均线买入，跌破均线卖出。

用法:
  quantix backtest run-file strategies/ma_breakout.py 588000.SH 1970-01-01 2026-04-18 --period 1D --adjust hfq
  quantix backtest run-file strategies/ma_breakout.py 588000.SH 1970-01-01 2026-04-18 --period 1D --adjust hfq --params '{"period":10}'
"""


def initialize(context):
    context.ma_period = context.params.get("period", 20)
    context.bought = False


def handle_bar(context):
    ind = context.indicators
    if ind is None:
        return

    ma = ind.ma(context.ma_period)
    if ma == 0.0:
        return

    price = context.current_price(context.symbol)
    if price <= 0:
        return

    pos = context.get_position(context.symbol)

    if not context.bought and price > ma:
        qty = int(context.cash * 0.9 / price / 100) * 100
        if qty > 0:
            context.buy(context.symbol, qty)
            context.bought = True

    elif context.bought and price < ma and pos > 0:
        context.sell(context.symbol, pos)
        context.bought = False

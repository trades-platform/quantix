"""加速度动量策略 (Momentum Acceleration)

比较短期动量与中期动量：
- 短期动量超过中期动量且为正时买入（动量加速上行）
- 短期动量低于中期动量或转负时卖出（动量减速或反转）

用法:
  quantix backtest run-file strategies/acceleration_momentum.py 510300.SH 2020-01-01 2026-04-24 --period 1D --adjust hfq
  quantix backtest run-file strategies/acceleration_momentum.py 510300.SH,510500.SH 2020-01-01 2026-04-24 --period 1D --adjust hfq --params '{"short_period":10,"long_period":30}'
"""


def initialize(context):
    context.short_period = context.params.get("short_period", 10)
    context.long_period = context.params.get("long_period", 30)


def handle_bar(context):
    for sym in context.symbols:
        ind = context.indicators_for(sym)
        if ind is None:
            continue

        short_roc = ind.roc(context.short_period)
        long_roc = ind.roc(context.long_period)

        if short_roc == 0.0 or long_roc == 0.0:
            continue

        price = context.current_price(sym)
        if price <= 0:
            continue

        pos = context.get_position(sym)

        if pos == 0 and short_roc > long_roc and short_roc > 0:
            qty = int(context.cash * 0.9 / price / 100) * 100
            if qty > 0:
                context.buy(sym, qty)

        elif pos > 0 and (short_roc < long_roc or short_roc < 0):
            context.sell(sym, pos)

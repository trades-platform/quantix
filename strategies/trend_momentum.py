"""趋势动量策略

以均线作为趋势过滤器，结合近期收益率（动量）进行择时：
- 价格站上均线且动量超过阈值时买入（趋势向上且有动能）。
- 价格跌破均线或动量转负时卖出（趋势结束或动能衰竭）。

适用标的：宽基ETF、行业ETF等流动性较好的品种。

用法:
  quantix backtest run-file strategies/trend_momentum.py 159869.SZ 2020-01-01 2026-04-24 --period 1D --adjust hfq
  quantix backtest run-file strategies/trend_momentum.py 159869.SZ 2020-01-01 2026-04-24 --period 1D --adjust hfq --params '{"ma_period":20,"momentum_period":20,"momentum_threshold":0.03}'
"""


def initialize(context):
    context.ma_period = context.params.get("ma_period", 20)
    context.momentum_period = context.params.get("momentum_period", 20)
    context.momentum_threshold = context.params.get("momentum_threshold", 0.03)


def handle_bar(context):
    for sym in context.symbols:
        ind = context.indicators_for(sym)
        if ind is None:
            continue

        price = context.current_price(sym)
        if price <= 0:
            continue

        ma = ind.ma(context.ma_period)
        if ma == 0.0:
            continue

        momentum = ind.roc(context.momentum_period)
        if momentum == 0.0:
            continue

        pos = context.get_position(sym)

        if pos == 0 and price > ma and momentum > context.momentum_threshold:
            qty = int(context.cash * 0.9 / price / 100) * 100
            if qty > 0:
                context.buy(sym, qty)

        elif pos > 0 and (price < ma or momentum < 0):
            context.sell(sym, pos)

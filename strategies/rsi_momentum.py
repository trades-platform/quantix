"""RSI动量策略

利用RSI相对强弱指标判断动量极端状态：
- RSI 低于超卖阈值时买入（动能衰竭后的反弹预期）
- RSI 高于超买阈值时卖出（动能过热后的回落预期）

用法:
  quantix backtest run-file strategies/rsi_momentum.py 510300.SH 2020-01-01 2026-04-24 --period 1D --adjust hfq
  quantix backtest run-file strategies/rsi_momentum.py 510300.SH 2020-01-01 2026-04-24 --period 1D --adjust hfq --params '{"rsi_period":14,"oversold":30,"overbought":70}'
"""

import numpy as np


def initialize(context):
    context.rsi_period = context.params.get("rsi_period", 14)
    context.oversold = context.params.get("oversold", 30)
    context.overbought = context.params.get("overbought", 70)


def handle_bar(context):
    for sym in context.symbols:
        ind = context.indicators_for(sym)
        if ind is None:
            continue

        rsi = ind.rsi(context.rsi_period)
        if np.isnan(rsi):
            continue

        price = context.current_price(sym)
        if price <= 0:
            continue

        pos = context.get_position(sym)

        if pos == 0 and rsi < context.oversold:
            qty = int(context.cash * 0.9 / price / 100) * 100
            if qty > 0:
                context.buy(sym, qty)

        elif pos > 0 and rsi > context.overbought:
            context.sell(sym, pos)

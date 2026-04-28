"""双动量策略 (Dual Momentum)

基于 Gary Antonacci 的双动量理论：
- 绝对动量 (abs_window)：标的自身长期收益 > 0 才视为候选，规避熊市；
- 相对动量 (rel_window)：在通过绝对动量过滤的候选中，选 rel_window 区间收益最大者持有。

注意事项（避免被交易成本磨平收益）：
- 默认 ``rebalance_period=20``（约一个月）。日线策略不要按 1 频率换仓，否则相邻
  排名会反复触发买卖，往返成本（2×佣金 + 2×滑点 ≈ 0.3%）几次就吃光预期收益。
- ``min_advantage`` 是切换迟滞带：只有当新冠军比当前持仓的相对动量高出至少
  ``min_advantage`` 才换仓，进一步抑制噪声切换。
"""


def initialize(context):
    context.abs_window = int(context.params.get("abs_window", 126))
    context.rel_window = int(context.params.get("rel_window", 126))
    context.rebalance_period = int(context.params.get("rebalance_period", 20))
    context.min_advantage = float(context.params.get("min_advantage", 0.01))
    context.target_weight = float(context.params.get("target_weight", 0.95))


def _momentum(hist, window):
    if len(hist) <= window or hist[-1 - window] <= 0:
        return None
    return (hist[-1] - hist[-1 - window]) / hist[-1 - window]


def handle_bar(context):
    if context.bar_index % context.rebalance_period != 0:
        return

    need = max(context.abs_window, context.rel_window) + 1

    # 1. 收集通过绝对动量过滤的候选 (sym, rel_return)
    candidates = []
    rel_lookup = {}
    for sym in context.symbols:
        ind = context.indicators_for(sym)
        if ind is None:
            continue
        hist = ind.history("close", need)
        if len(hist) < need:
            continue
        abs_ret = _momentum(hist, context.abs_window)
        rel_ret = _momentum(hist, context.rel_window)
        if abs_ret is None or rel_ret is None:
            continue
        rel_lookup[sym] = rel_ret
        if abs_ret > 0:
            candidates.append((sym, rel_ret))

    # 2. 选相对动量最强者
    target_sym = None
    target_ret = -float("inf")
    for sym, ret in candidates:
        if ret > target_ret:
            target_ret = ret
            target_sym = sym

    # 3. 当前持仓
    current_holdings = [s for s in context.symbols if context.get_position(s) > 0]

    # 4. 迟滞带：新冠军优势不足且当前持仓仍合格则保持
    if target_sym is not None and len(current_holdings) == 1:
        held = current_holdings[0]
        if held in rel_lookup and target_sym != held:
            held_ret = rel_lookup[held]
            if target_ret - held_ret < context.min_advantage:
                if any(s == held for s, _ in candidates):
                    return

    # 5. 卖掉非目标持仓
    for sym in current_holdings:
        if sym != target_sym:
            context.sell(sym, context.get_position(sym))

    # 6. 买入目标
    if target_sym is None:
        return
    if context.get_position(target_sym) > 0:
        return

    price = context.current_price(target_sym)
    if price <= 0:
        return

    # 用总权益估算仓位（卖单成交后 cash 才回补）。target_weight<1 预留佣金/滑点缓冲。
    equity = context.portfolio_value or context.cash
    qty = int(equity * context.target_weight / price / 100) * 100
    if qty > 0:
        context.buy(target_sym, qty)

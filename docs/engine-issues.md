# 回测引擎待修复问题

## 1. 执行价格过于乐观

**现状**：策略在 bar N 收盘价生成信号，同一根 bar 收盘价成交。

**问题**：实际交易中看到收盘价后下单，最快在 bar N+1 开盘价成交，存在 0.1-0.5% 差异。这并非前视偏差，而是一种乐观的执行模型，会虚增收益。

**修复方案**：订单延迟到下一根 bar 开盘价成交。需要重构 bar 循环，将信号生成和订单执行拆到不同 bar。

**涉及文件**：`backend/engine/backtest.py`

---

## 2. 无滑点模型

**现状**：以当前 bar 收盘价精确成交，零滑点。

**问题**：实际交易存在滑点（特别是市价单），ETF 一般 0.1-0.2%。35 笔交易累计影响显著。

**修复方案**：`BacktestEngine` 增加 `slippage: float` 参数（默认 0.001），买入价 = 当前价 × (1 + slippage)，卖出价 = 当前价 × (1 - slippage)。

**涉及文件**：`backend/engine/backtest.py`、`backend/engine/context.py`

---

## 3. 胜率未计入佣金

**现状**：`metrics.py` 中 `_group_round_trips()` 的盈亏计算不包含佣金。单笔交易可能毛利为正但扣除佣金后为负，仍被计为"盈利"。

**问题**：胜率和盈亏比被高估。

**修复方案**：往返盈亏计算中累加买入和卖出的佣金，净盈亏 = 毛盈亏 - 买入佣金 - 卖出佣金。

**涉及文件**：`backend/engine/metrics.py`

---

## 4. 指标对象每轮重建

**现状**：每个 bar 为每个标的创建新的 `SymbolIndicators` 对象，对完整历史切片做 `iloc[:idx]`。

**问题**：短周期简单 MA 无影响，但长周期 MACD、KDJ 计算成本高，1314 bars 下可能成为瓶颈。

**修复方案**：增量计算或缓存机制，避免每轮全量重算。

**涉及文件**：`backend/engine/backtest.py`、`backend/engine/indicators.py`

---

## 5. 策略仓位标志与引擎不同步

**现状**：策略用布尔型 `context.bought` 跟踪持仓状态。如果买入因资金不足被引擎拒绝，`bought` 已设为 True 但实际没持仓。

**问题**：后续 bar 进入卖出分支，尝试卖出零仓位静默失败，然后 `bought` 变回 False，可能错过正确的入场时机。

**修复方案**：策略层面应使用 `context.get_position(symbol) > 0` 替代布尔标志。引擎层面可在 `buy()` 失败时通知策略（回调或返回值）。

**涉及文件**：策略文件、`backend/engine/context.py`

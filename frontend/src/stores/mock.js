// Mock data for development and testing
export const mockStrategies = [
  {
    id: '1',
    name: '双均线策略',
    description: '基于5日和20日均线的交叉信号，金叉买入死叉卖出',
    code: `# 双均线策略

def initialize(context):
    context.short_period = 5
    context.long_period = 20

def handle_bar(context, bar):
    data = context.history(length=context.long_period)
    if len(data) < context.long_period:
        return []

    short_ma = data['close'].tail(context.short_period).mean()
    long_ma = data['close'].tail(context.long_period).mean()
    position = context.position

    orders = []
    if short_ma > long_ma and position == 0:
        orders.append({'symbol': context.symbol, 'side': 'buy', 'quantity': 100})
    elif short_ma < long_ma and position > 0:
        orders.append({'symbol': context.symbol, 'side': 'sell', 'quantity': position})

    return orders
`,
    created_at: '2024-01-15T10:30:00Z',
    updated_at: '2024-01-15T10:30:00Z'
  },
  {
    id: '2',
    name: 'MACD策略',
    description: '基于MACD指标的趋势跟踪策略',
    code: `# MACD策略

def initialize(context):
    context.fast_period = 12
    context.slow_period = 26
    context.signal_period = 9

def handle_bar(context, bar):
    data = context.history(length=context.slow_period + context.signal_period)
    if len(data) < context.slow_period + context.signal_period:
        return []

    close = data['close']
    ema_fast = close.ewm(span=context.fast_period).mean()
    ema_slow = close.ewm(span=context.slow_period).mean()
    macd = ema_fast - ema_slow
    signal = macd.ewm(span=context.signal_period).mean()

    position = context.position
    orders = []

    if macd.iloc[-1] > signal.iloc[-1] and macd.iloc[-2] <= signal.iloc[-2]:
        if position == 0:
            orders.append({'symbol': context.symbol, 'side': 'buy', 'quantity': 100})
    elif macd.iloc[-1] < signal.iloc[-1] and macd.iloc[-2] >= signal.iloc[-2]:
        if position > 0:
            orders.append({'symbol': context.symbol, 'side': 'sell', 'quantity': position})

    return orders
`,
    created_at: '2024-01-20T14:20:00Z',
    updated_at: '2024-01-20T14:20:00Z'
  },
  {
    id: '3',
    name: 'RSI策略',
    description: '基于RSI指标的超买超卖策略',
    code: `# RSI策略

def initialize(context):
    context.rsi_period = 14
    context.overbought = 70
    context.oversold = 30

def handle_bar(context, bar):
    data = context.history(length=context.rsi_period + 1)
    if len(data) < context.rsi_period + 1:
        return []

    close = data['close']
    delta = close.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.rolling(window=context.rsi_period).mean()
    avg_loss = loss.rolling(window=context.rsi_period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    current_rsi = rsi.iloc[-1]

    position = context.position
    orders = []

    if current_rsi < context.oversold and position == 0:
        orders.append({'symbol': context.symbol, 'side': 'buy', 'quantity': 100})
    elif current_rsi > context.overbought and position > 0:
        orders.append({'symbol': context.symbol, 'side': 'sell', 'quantity': position})

    return orders
`,
    created_at: '2024-02-01T09:15:00Z',
    updated_at: '2024-02-01T09:15:00Z'
  }
]

export const mockSymbols = [
  { symbol: '600000.SH', name: '浦发银行', data_type: 'stock', row_count: 1250, latest_timestamp: '2024-04-15T15:00:00Z' },
  { symbol: '600036.SH', name: '招商银行', data_type: 'stock', row_count: 1180, latest_timestamp: '2024-04-15T15:00:00Z' },
  { symbol: '600519.SH', name: '贵州茅台', data_type: 'stock', row_count: 1320, latest_timestamp: '2024-04-15T15:00:00Z' },
  { symbol: '600887.SH', name: '伊利股份', data_type: 'stock', row_count: 1100, latest_timestamp: '2024-04-15T15:00:00Z' },
  { symbol: '000001.SZ', name: '平安银行', data_type: 'stock', row_count: 1280, latest_timestamp: '2024-04-15T15:00:00Z' },
  { symbol: '000002.SZ', name: '万科A', data_type: 'stock', row_count: 1150, latest_timestamp: '2024-04-15T15:00:00Z' },
  { symbol: '000333.SZ', name: '美的集团', data_type: 'stock', row_count: 1050, latest_timestamp: '2024-04-15T15:00:00Z' },
  { symbol: '000858.SZ', name: '五粮液', data_type: 'stock', row_count: 1190, latest_timestamp: '2024-04-15T15:00:00Z' },
  { symbol: '300001.SZ', name: '特锐德', data_type: 'stock', row_count: 980, latest_timestamp: '2024-04-15T15:00:00Z' },
  { symbol: '300750.SZ', name: '宁德时代', data_type: 'stock', row_count: 850, latest_timestamp: '2024-04-15T15:00:00Z' }
]

export const generateMockKlineData = (symbol = '600000.SH', days = 100) => {
  const data = []
  let price = 10 + Math.random() * 10
  const now = new Date()

  for (let i = days; i >= 0; i--) {
    const date = new Date(now)
    date.setDate(date.getDate() - i)

    const volatility = 0.02
    const change = (Math.random() - 0.5) * 2 * volatility

    const open = price
    const close = price * (1 + change)
    const high = Math.max(open, close) * (1 + Math.random() * volatility)
    const low = Math.min(open, close) * (1 - Math.random() * volatility)
    const volume = Math.floor(1000000 + Math.random() * 9000000)

    data.push({
      timestamp: date.toISOString().split('T')[0],
      open: parseFloat(open.toFixed(2)),
      high: parseFloat(high.toFixed(2)),
      low: parseFloat(low.toFixed(2)),
      close: parseFloat(close.toFixed(2)),
      volume
    })

    price = close
  }

  return data
}

export const mockBacktestResult = {
  id: 'bt-001',
  symbol: '600000.SH',
  start_date: '2023-01-01',
  end_date: '2024-01-01',
  initial_capital: 1000000,
  status: 'completed',
  total_return: 0.1567,
  annual_return: 0.1523,
  sharpe_ratio: 1.23,
  max_drawdown: -0.0892,
  win_rate: 0.58,
  equity_curve: JSON.stringify(
    Array.from({ length: 50 }, (_, i) => ({
      date: `2023-${String(Math.floor(i / 4) + 1).padStart(2, '0')}-${String((i % 28) + 1).padStart(2, '0')}`,
      value: 1000000 * (1 + 0.1567 * (i / 49)),
      daily_return: (Math.random() - 0.4) * 0.02
    }))
  ),
  monthly_returns: JSON.stringify(
    Array.from({ length: 12 }, (_, i) => ({
      month: `2023-${String(i + 1).padStart(2, '0')}`,
      return: (Math.random() - 0.3) * 0.1
    }))
  ),
  created_at: '2024-01-15T10:30:00Z'
}

export const mockTrades = [
  {
    id: 't1',
    timestamp: '2023-02-15T09:30:00Z',
    symbol: '600000.SH',
    side: 'buy',
    price: 10.5,
    quantity: 100,
    profit: 520
  },
  {
    id: 't2',
    timestamp: '2023-03-20T14:30:00Z',
    symbol: '600000.SH',
    side: 'sell',
    price: 10.8,
    quantity: 100,
    profit: null
  },
  {
    id: 't3',
    timestamp: '2023-04-10T10:00:00Z',
    symbol: '600000.SH',
    side: 'buy',
    price: 10.6,
    quantity: 100,
    profit: -180
  },
  {
    id: 't4',
    timestamp: '2023-05-15T13:30:00Z',
    symbol: '600000.SH',
    side: 'sell',
    price: 10.5,
    quantity: 100,
    profit: null
  },
  {
    id: 't5',
    timestamp: '2023-06-20T11:00:00Z',
    symbol: '600000.SH',
    side: 'buy',
    price: 10.7,
    quantity: 100,
    profit: 340
  },
  {
    id: 't6',
    timestamp: '2023-07-25T14:00:00Z',
    symbol: '600000.SH',
    side: 'sell',
    price: 11.0,
    quantity: 100,
    profit: null
  }
]

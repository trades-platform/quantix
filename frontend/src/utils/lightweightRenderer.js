/**
 * Lightweight Charts renderer (v5) — consumes quantix's chart payload shape:
 *   ohlcv:      [{ timestamp, open, high, low, close, volume }, ...]
 *   indicators: [{ name, pane, kind, color, data: {type, values|upper/middle/lower/extra} }, ...]
 *   trades:     [{ side: 'buy'|'sell', price, timestamp }, ...]
 *
 * Pane layout: pane 0 = price (with 'main' LINE/BAND overlays); then 'volume';
 * then any other named panes (macd/rsi/kdj/atr/equity/drawdown) in first-seen
 * order. Indicator `kind` ∈ line|histogram|band|markers; `data.type` ∈ scalar|band.
 *
 * Interaction (ported from bit-market's lightweightRenderer):
 *   - Crosshair tooltip: OHLC + change-vs-prev-close + main-pane overlay values.
 *   - Right-button drag selects a range; a floating panel reports bar count,
 *     change %, amplitude %, high/low/average for the selection. Drag the box
 *     edges or body to adjust; left-click empty space to clear.
 */
import {
  createChart,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  createSeriesMarkers,
} from 'lightweight-charts'

// Band sub-line palette (for BOLL upper/lower, KDJ k/d/j, etc.)
const SUB_COLORS = ['#2196F3', '#FF9800', '#AB47BC', '#26a69a', '#ef5350']

function themeColors(dark) {
  // Chinese convention: 红涨绿跌 (up = red, down = green).
  return dark
    ? { bg: '#131722', text: '#d1d4dc', grid: '#2B2B43', up: '#ef5350', down: '#26a69a' }
    : { bg: '#ffffff', text: '#333333', grid: '#e0e0e0', up: '#ef5350', down: '#26a69a' }
}

/** Split an ISO-ish timestamp into { date: 'YYYY-MM-DD', time: 'HH:MM:SS'|null }. */
function parseTimestamp(s) {
  const [date, time] = String(s).split(/[ T]/)
  return { date, time: time || null }
}

/** Date-only stays a business-day string; intraday → UTC unix seconds so every
 *  bar has a unique, strictly-increasing value. */
function toTime(s) {
  const { date, time } = parseTimestamp(s)
  if (!time) return date
  const [y, mo, da] = date.split('-').map(Number)
  const [h, mi, se] = time.split(':').map(Number)
  return Date.UTC(y, mo - 1, da, h, mi, se || 0) / 1000
}

export function createLightweightRenderer(el, opts = {}) {
  const dark = opts.darkMode !== false
  const COLORS = themeColors(dark)
  const UP = COLORS.up
  const DOWN = COLORS.down

  let pricePrecision = 2
  let candleSeries = null
  let markersPrimitive = null
  // Main-pane overlay lines tracked for the crosshair tooltip.
  let overlaySeries = []
  let prevCloseByTime = new Map()
  let lastTimes = []
  let lastOhlcv = []
  let lastDates = []

  const chart = createChart(el, {
    width: el.clientWidth || 600,
    height: el.clientHeight || 400,
    layout: { background: { color: COLORS.bg }, textColor: COLORS.text },
    grid: { vertLines: { color: COLORS.grid }, horzLines: { color: COLORS.grid } },
    crosshair: { mode: 1 }, // Normal
    rightPriceScale: { borderVisible: false },
    timeScale: { borderVisible: false, timeVisible: false },
  })

  el.style.position = 'relative'

  function formatPrice(p) {
    return Number(p).toFixed(pricePrecision)
  }
  function formatVolume(v) {
    const a = Math.abs(v)
    if (a >= 1e8) return `${(v / 1e8).toFixed(1)}亿`
    if (a >= 1e4) return `${(v / 1e4).toFixed(1)}万`
    return `${Math.round(v)}`
  }

  // --- Crosshair tooltip ---
  const tooltip = document.createElement('div')
  tooltip.style.cssText =
    'position:absolute;z-index:20;pointer-events:none;font-size:12px;line-height:1.7;' +
    `color:${COLORS.text};background:rgba(${dark ? '19,23,34' : '255,255,255'},0.92);` +
    'padding:6px 10px;border-radius:6px;box-shadow:0 2px 8px rgba(0,0,0,0.12);' +
    'display:none;white-space:nowrap;border:1px solid ' + COLORS.grid + ';'
  el.appendChild(tooltip)

  function timeLabel(t) {
    if (t == null) return ''
    if (typeof t === 'number') {
      const d = new Date(t * 1000)
      const p = (n) => String(n).padStart(2, '0')
      const base = `${d.getUTCFullYear()}-${p(d.getUTCMonth() + 1)}-${p(d.getUTCDate())}`
      return chart.options().timeScale.timeVisible
        ? `${base} ${p(d.getUTCHours())}:${p(d.getUTCMinutes())}`
        : base
    }
    return String(t)
  }

  chart.subscribeCrosshairMove((param) => {
    if (brushActive || !param.time || !param.point || !candleSeries) {
      tooltip.style.display = 'none'
      return
    }
    const data = param.seriesData.get(candleSeries)
    if (!data) {
      tooltip.style.display = 'none'
      return
    }
    const prev = prevCloseByTime.get(param.time)
    let chgSpan = '<span style="color:#999">—</span>'
    if (typeof prev === 'number' && prev !== 0) {
      const chg = ((data.close - prev) / prev) * 100
      const c = chg >= 0 ? UP : DOWN
      chgSpan = `<span style="color:${c}">${chg >= 0 ? '+' : ''}${chg.toFixed(2)}%</span>`
    }
    const closeColor = data.open != null && data.close >= data.open ? UP : DOWN
    let maHtml = ''
    for (const { label, color, series } of overlaySeries) {
      const v = param.seriesData.get(series)
      if (v && v.value != null) {
        maHtml += `<div><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${color};margin-right:4px;vertical-align:middle;"></span><span style="color:${color}">${label}</span> <b>${v.value.toFixed(3)}</b></div>`
      }
    }
    tooltip.innerHTML =
      `<div style="margin-bottom:2px;color:#999;font-weight:500">${timeLabel(param.time)}</div>` +
      `<div>开 <b>${formatPrice(data.open)}</b>  高 <b>${formatPrice(data.high)}</b></div>` +
      `<div>低 <b>${formatPrice(data.low)}</b>  收 <b style="color:${closeColor}">${formatPrice(data.close)}</b> ${chgSpan}</div>` +
      maHtml

    const offX = 16, offY = 16
    const tw = tooltip.offsetWidth || 150
    const th = tooltip.offsetHeight || 80
    let left = param.point.x + offX
    let top = param.point.y + offY
    if (left + tw > el.clientWidth) left = param.point.x - tw - offX
    if (top + th > el.clientHeight) top = param.point.y - th - offY
    tooltip.style.left = `${Math.max(0, left)}px`
    tooltip.style.top = `${Math.max(0, top)}px`
    tooltip.style.display = 'block'
  })

  // --- Range selection with draggable edges (ported from bit-market) ---
  let brushActive = false
  let startX = 0
  let draggingEdge = null // 'left' | 'right' | 'body' | null
  let dragStartMouseX = 0
  let dragStartLeft = 0
  let dragStartWidth = 0
  const DRAG_THRESHOLD = 6
  let pendingSelect = false
  let activeSelect = false
  let leftDownX = null
  let leftMoved = false

  const overlay = document.createElement('div')
  overlay.style.cssText =
    'position:absolute;top:0;height:100%;background:rgba(41,98,255,0.08);' +
    'border-left:1px solid #2962FF;border-right:1px solid #2962FF;' +
    'pointer-events:none;display:none;z-index:10;'
  el.appendChild(overlay)

  const handleStyle =
    'position:absolute;top:0;width:6px;height:100%;cursor:ew-resize;pointer-events:auto;z-index:11;'
  const leftHandle = document.createElement('div')
  leftHandle.style.cssText = handleStyle + 'left:-3px;'
  overlay.appendChild(leftHandle)
  const rightHandle = document.createElement('div')
  rightHandle.style.cssText = handleStyle + 'right:-3px;'
  overlay.appendChild(rightHandle)
  const bodyHandle = document.createElement('div')
  bodyHandle.style.cssText =
    'position:absolute;top:0;left:6px;right:6px;height:100%;cursor:grab;pointer-events:auto;z-index:10;'
  overlay.appendChild(bodyHandle)

  const rangeTooltip = document.createElement('div')
  rangeTooltip.style.cssText =
    'position:absolute;z-index:22;pointer-events:none;font-size:12px;line-height:1.8;' +
    `color:${COLORS.text};background:rgba(${dark ? '19,23,34' : '255,255,255'},0.92);` +
    'padding:6px 10px;border-radius:6px;box-shadow:0 2px 8px rgba(0,0,0,0.12);' +
    'display:none;white-space:nowrap;border:1px solid #2962FF;'
  el.appendChild(rangeTooltip)

  function hideRangeStats() {
    rangeTooltip.style.display = 'none'
  }
  function clearSelection() {
    overlay.style.display = 'none'
    brushActive = false
    hideRangeStats()
  }

  /** Map a container-relative pixel X to a fractional bar index. lightweight-charts'
   *  coordinateToLogical CEILs internally (off-by-one), so we interpolate between
   *  two integer logical anchors instead. Pane-logical origin sits at the right
   *  edge of the (empty) left price scale, so shift by its width. */
  function xToFloatIndex(x) {
    const ts = chart.timeScale()
    const n = lastOhlcv.length
    if (n === 0) return null
    const vr = ts.getVisibleLogicalRange()
    if (!vr) return null
    const paneX = x - chart.priceScale('left').width()
    const i0 = Math.max(0, Math.min(n - 1, Math.floor(vr.from)))
    const i1 = Math.max(0, Math.min(n - 1, Math.ceil(vr.to)))
    const x0 = ts.logicalToCoordinate(i0)
    const x1 = i0 < i1 ? ts.logicalToCoordinate(i1) : null
    if (x0 == null || x1 == null || x1 === x0) return i0
    return i0 + ((paneX - x0) / (x1 - x0)) * (i1 - i0)
  }

  /** Resolve the overlay box to a clamped [start, end] bar span, or null when
   *  it sits entirely outside the data. */
  function currentSelectionIndices() {
    if (lastOhlcv.length === 0) return null
    const left = parseFloat(overlay.style.left)
    const width = parseFloat(overlay.style.width)
    if (!isFinite(left) || !isFinite(width) || width <= 0) return null
    const fStart = xToFloatIndex(left)
    const fEnd = xToFloatIndex(left + width)
    if (fStart == null || fEnd == null) return null
    let start = Math.round(fStart)
    let end = Math.round(fEnd)
    if (start > end) [start, end] = [end, start]
    const last = lastOhlcv.length - 1
    if (end < 0 || start > last) return null
    return { start: Math.max(0, start), end: Math.min(last, end) }
  }

  function showRangeStats() {
    const sel = currentSelectionIndices()
    if (!sel) {
      rangeTooltip.style.display = 'none'
      return
    }
    const fromTime = lastDates[sel.start]
    const toTime = lastDates[sel.end]
    const closes = lastOhlcv.slice(sel.start, sel.end + 1).map((d) => d.close)
    const highs = lastOhlcv.slice(sel.start, sel.end + 1).map((d) => d.high)
    const lows = lastOhlcv.slice(sel.start, sel.end + 1).map((d) => d.low)
    const firstClose = closes[0]
    const lastClose = closes[closes.length - 1]
    const high = Math.max(...highs)
    const low = Math.min(...lows)
    const chgPct = firstClose ? ((lastClose - firstClose) / firstClose) * 100 : 0
    const ampPct = low ? ((high - low) / low) * 100 : 0
    const avg = closes.reduce((a, b) => a + b, 0) / closes.length
    const chgColor = chgPct >= 0 ? UP : DOWN

    // Keep date+HH:MM prefix regardless of separator variants; drop seconds.
    const fmt = (s) => (/^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}/.test(s) ? s.slice(0, 16) : s)

    rangeTooltip.innerHTML =
      `<div style="margin-bottom:2px;color:#2962FF;font-weight:500">起 ${fmt(fromTime)}</div>` +
      `<div style="margin-bottom:2px;color:#2962FF;font-weight:500">止 ${fmt(toTime)}</div>` +
      `<div>${closes.length} 根</div>` +
      `<div>涨跌 <b style="color:${chgColor}">${chgPct >= 0 ? '+' : ''}${chgPct.toFixed(2)}%</b></div>` +
      `<div>振幅 <b>${ampPct.toFixed(2)}%</b></div>` +
      `<div>最高 <b>${high.toFixed(3)}</b></div>` +
      `<div>最低 <b>${low.toFixed(3)}</b></div>` +
      `<div>均价 <b>${avg.toFixed(3)}</b></div>`

    const left = parseFloat(overlay.style.left)
    const width = parseFloat(overlay.style.width)
    const right = left + width
    const gap = 8
    const ttW = rangeTooltip.offsetWidth || 130
    const ttH = rangeTooltip.offsetHeight || 210
    let ttLeft
    if (right + gap + ttW <= el.clientWidth) ttLeft = right + gap
    else if (left - gap - ttW >= 0) ttLeft = left - gap - ttW
    else if (el.clientWidth - right >= left) ttLeft = Math.min(el.clientWidth - ttW - 4, right + gap)
    else ttLeft = Math.max(4, left - gap - ttW)
    let ttTop = (el.clientHeight - ttH) / 2
    ttTop = Math.max(4, Math.min(ttTop, el.clientHeight - ttH - 4))
    rangeTooltip.style.left = `${ttLeft}px`
    rangeTooltip.style.top = `${ttTop}px`
    rangeTooltip.style.display = 'block'
  }

  // Edge / body drag
  function onHandleDown(edge) {
    return (e) => {
      e.stopPropagation()
      e.preventDefault()
      draggingEdge = edge
      dragStartMouseX = e.clientX
      dragStartLeft = parseFloat(overlay.style.left)
      dragStartWidth = parseFloat(overlay.style.width)
      if (edge === 'body') bodyHandle.style.cursor = 'grabbing'
    }
  }
  leftHandle.addEventListener('mousedown', onHandleDown('left'))
  rightHandle.addEventListener('mousedown', onHandleDown('right'))
  bodyHandle.addEventListener('mousedown', onHandleDown('body'))

  function onDocMouseMove(e) {
    if (!draggingEdge) return
    const dx = e.clientX - dragStartMouseX
    if (draggingEdge === 'left') {
      const newLeft = Math.max(0, dragStartLeft + dx)
      const newWidth = dragStartWidth - (newLeft - dragStartLeft)
      if (newWidth > 10) {
        overlay.style.left = `${newLeft}px`
        overlay.style.width = `${newWidth}px`
      }
    } else if (draggingEdge === 'right') {
      overlay.style.width = `${Math.max(10, dragStartWidth + dx)}px`
    } else if (draggingEdge === 'body') {
      overlay.style.left = `${Math.max(0, dragStartLeft + dx)}px`
    }
    showRangeStats()
  }
  function onDocMouseUp() {
    if (!draggingEdge) return
    if (draggingEdge === 'body') bodyHandle.style.cursor = 'grab'
    draggingEdge = null
    showRangeStats()
  }
  document.addEventListener('mousemove', onDocMouseMove)
  document.addEventListener('mouseup', onDocMouseUp)

  function elX(e) {
    return e.clientX - el.getBoundingClientRect().left
  }

  // Right-button drives range selection; suppress the context menu and any
  // right-button mouse gesture so the gesture only affects the chart.
  function onContextMenu(e) {
    e.preventDefault()
  }
  function onAuxClick(e) {
    if (e.button === 2) e.preventDefault()
  }
  function onSelectMouseDown(e) {
    if (e.button !== 2 || draggingEdge) return
    e.preventDefault()
    pendingSelect = true
    activeSelect = false
    startX = elX(e)
    brushActive = false
  }
  function onSelectMouseMove(e) {
    if (!pendingSelect) return
    const currentX = elX(e)
    if (!activeSelect) {
      if (Math.abs(currentX - startX) < DRAG_THRESHOLD) return
      activeSelect = true
      brushActive = true
      overlay.style.display = 'block'
    }
    overlay.style.left = `${Math.min(startX, currentX)}px`
    overlay.style.width = `${Math.abs(currentX - startX)}px`
    showRangeStats()
  }
  function onSelectMouseUp(e) {
    if (e.button === 2) e.preventDefault()
    if (!pendingSelect) return
    pendingSelect = false
    if (!activeSelect) {
      clearSelection()
      return
    }
    activeSelect = false
    showRangeStats()
  }
  el.addEventListener('contextmenu', onContextMenu)
  el.addEventListener('auxclick', onAuxClick)
  el.addEventListener('mousedown', onSelectMouseDown)
  el.addEventListener('mousemove', onSelectMouseMove)
  el.addEventListener('mouseup', onSelectMouseUp)

  // A plain left click on empty space clears an existing selection. Left-drag
  // still pans the chart, so only a click that stays within the drag threshold
  // (i.e. not a pan) clears. Handle/edge clicks stopPropagation, so they won't
  // reach this listener.
  function onClearMouseDown(e) {
    if (e.button !== 0 || draggingEdge) return
    leftDownX = elX(e)
    leftMoved = false
  }
  function onClearMouseMove(e) {
    if (leftDownX == null) return
    if (Math.abs(elX(e) - leftDownX) > DRAG_THRESHOLD) leftMoved = true
  }
  function onClearMouseUp(e) {
    if (e.button !== 0) return
    const wasClick = leftDownX != null && !leftMoved
    leftDownX = null
    leftMoved = false
    if (!wasClick || draggingEdge || overlay.style.display === 'none') return
    clearSelection()
  }
  el.addEventListener('mousedown', onClearMouseDown)
  el.addEventListener('mousemove', onClearMouseMove)
  el.addEventListener('mouseup', onClearMouseUp)

  // --- Helpers to build per-bar point arrays ---
  function linePoints(values, times) {
    const out = []
    for (let i = 0; i < values.length; i++) {
      const v = values[i]
      if (v == null || Number.isNaN(v)) out.push({ time: times[i] })
      else out.push({ time: times[i], value: v })
    }
    return out
  }
  function histPointsSign(values, times) {
    const out = []
    for (let i = 0; i < values.length; i++) {
      const v = values[i]
      if (v == null || Number.isNaN(v)) continue
      out.push({ time: times[i], value: v, color: v >= 0 ? UP : DOWN })
    }
    return out
  }

  function renderIndicator(ind, paneIdx, times, ohlcv) {
    const data = ind.data || {}
    const baseColor = ind.color || '#999'
    const isMacd = ind.name && ind.name.toUpperCase().startsWith('MACD')

    if (data.type === 'scalar') {
      const values = data.values || []
      if (ind.pane === 'volume') {
        const points = []
        for (let i = 0; i < values.length; i++) {
          const v = values[i]
          if (v == null || Number.isNaN(v)) continue
          const up = i === 0 || ohlcv[i].close >= ohlcv[i - 1].close
          points.push({ time: times[i], value: v, color: up ? UP : DOWN })
        }
        const s = chart.addSeries(
          HistogramSeries,
          { priceFormat: { type: 'custom', formatter: formatVolume, minMove: 1 }, priceScaleId: 'right', priceLineVisible: false },
          paneIdx,
        )
        s.setData(points)
      } else if (ind.kind === 'histogram') {
        const s = chart.addSeries(
          HistogramSeries,
          { priceScaleId: 'right', priceLineVisible: false },
          paneIdx,
        )
        s.setData(histPointsSign(values, times))
      } else {
        const s = chart.addSeries(
          LineSeries,
          { color: baseColor, lineWidth: 1, priceScaleId: 'right', priceLineVisible: false, lastValueVisible: false },
          paneIdx,
        )
        s.setData(linePoints(values, times))
        if (ind.pane === 'main') overlaySeries.push({ label: ind.name, color: baseColor, series: s })
      }
      return
    }

    if (data.type === 'band') {
      const parts = []
      if (data.upper) parts.push({ key: 'upper', values: data.upper, dashed: true })
      if (data.middle) parts.push({ key: 'middle', values: data.middle, dashed: false })
      if (data.lower) parts.push({ key: 'lower', values: data.lower, dashed: true })
      if (data.extra) for (const [k, v] of Object.entries(data.extra)) parts.push({ key: k, values: v, dashed: false })

      parts.forEach((part, si) => {
        const vals = part.values || []
        if (part.key === 'histogram') {
          const s = chart.addSeries(HistogramSeries, { priceScaleId: 'right', priceLineVisible: false }, paneIdx)
          s.setData(histPointsSign(vals, times))
          return
        }
        let lineColor = baseColor
        if (isMacd) {
          // Match bit-market: DIF = deep pink, DEA = forest green; histogram is sign-coloured.
          if (part.key === 'dif') lineColor = '#FF1493'
          else if (part.key === 'dea') lineColor = '#228B22'
        } else if (part.key !== 'middle') {
          lineColor = SUB_COLORS[si % SUB_COLORS.length]
        }
        const s = chart.addSeries(
          LineSeries,
          {
            color: lineColor,
            lineWidth: part.key === 'middle' ? 2 : 1,
            lineStyle: part.dashed ? 2 : 0,
            priceScaleId: 'right',
            priceLineVisible: false,
            lastValueVisible: false,
          },
          paneIdx,
        )
        s.setData(linePoints(vals, times))
        if (ind.pane === 'main') overlaySeries.push({ label: `${ind.name}:${part.key}`, color: lineColor, series: s })
      })
    }
  }

  function render({ ohlcv, indicators, trades }) {
    // v5 has no clear-all: remove every existing series/markers before re-adding.
    for (const s of chart.panes().flatMap((p) => p.getSeries())) chart.removeSeries(s)
    markersPrimitive = null
    overlaySeries = []
    candleSeries = null
    clearSelection()

    if (!ohlcv || ohlcv.length === 0) return

    lastOhlcv = ohlcv
    lastDates = ohlcv.map((d) => String(d.timestamp))
    const times = ohlcv.map((d) => toTime(d.timestamp))
    lastTimes = times
    const isIntraday = ohlcv.some((d) => {
      const { time } = parseTimestamp(d.timestamp)
      return !!time && !/^00:00(:00)?$/.test(time)
    })
    chart.applyOptions({ timeScale: { timeVisible: isIntraday, secondsVisible: false } })

    let maxPrice = 0
    for (const d of ohlcv) {
      const a = Math.abs(d.high)
      if (Number.isFinite(a) && a > maxPrice) maxPrice = a
    }
    pricePrecision = maxPrice >= 1000 ? 1 : maxPrice >= 100 ? 2 : 3

    const candle = chart.addSeries(CandlestickSeries, {
      upColor: UP,
      downColor: DOWN,
      borderUpColor: UP,
      borderDownColor: DOWN,
      wickUpColor: UP,
      wickDownColor: DOWN,
      priceScaleId: 'right',
      priceFormat: { type: 'custom', formatter: formatPrice, minMove: Math.pow(10, -pricePrecision) },
    })
    candleSeries = candle
    candle.setData(
      ohlcv.map((d, i) => ({ time: times[i], open: d.open, high: d.high, low: d.low, close: d.close })),
    )

    prevCloseByTime = new Map()
    for (let i = 0; i < times.length; i++) {
      prevCloseByTime.set(times[i], i > 0 ? ohlcv[i - 1].close : null)
    }

    const paneGroups = new Map()
    for (const ind of indicators || []) {
      const p = ind.pane || 'main'
      if (!paneGroups.has(p)) paneGroups.set(p, [])
      paneGroups.get(p).push(ind)
    }
    // Pane 0 is always the price pane (candle + 'main' overlays). Sub-panes —
    // volume first, then other named panes — stack below from index 1. This
    // stays correct even when there are no 'main'-pane indicators (the candle
    // still owns pane 0, so volume never collides with the price pane).
    const subPanes = []
    if (paneGroups.has('volume')) subPanes.push('volume')
    for (const p of paneGroups.keys()) {
      if (p !== 'main' && p !== 'volume' && !subPanes.includes(p)) subPanes.push(p)
    }
    const paneIndex = new Map([['main', 0]])
    subPanes.forEach((p, i) => paneIndex.set(p, i + 1))

    for (const ind of paneGroups.get('main') || []) renderIndicator(ind, 0, times, ohlcv)
    for (const pane of subPanes) {
      for (const ind of paneGroups.get(pane)) renderIndicator(ind, paneIndex.get(pane), times, ohlcv)
    }

    if (trades && trades.length && candleSeries) {
      const timeByTs = new Map(ohlcv.map((d, i) => [String(d.timestamp), times[i]]))
      const markers = []
      for (const t of trades) {
        const time = timeByTs.get(String(t.timestamp))
        if (time == null) continue
        if (t.side === 'buy') {
          markers.push({ time, position: 'belowBar', color: UP, shape: 'arrowUp', text: 'B' })
        } else if (t.side === 'sell') {
          markers.push({ time, position: 'aboveBar', color: DOWN, shape: 'arrowDown', text: 'S' })
        }
      }
      if (markers.length) markersPrimitive = createSeriesMarkers(candleSeries, markers)
    }

    chart.timeScale().fitContent()

    const panes = chart.panes()
    if (panes.length > 1) {
      panes[0].setStretchFactor(3)
      for (let i = 1; i < panes.length; i++) panes[i].setStretchFactor(1)
    }
  }

  function resize() {
    chart.resize(el.clientWidth || 600, el.clientHeight || 400)
  }

  function dispose() {
    document.removeEventListener('mousemove', onDocMouseMove)
    document.removeEventListener('mouseup', onDocMouseUp)
    el.removeEventListener('contextmenu', onContextMenu)
    el.removeEventListener('auxclick', onAuxClick)
    el.removeEventListener('mousedown', onSelectMouseDown)
    el.removeEventListener('mousemove', onSelectMouseMove)
    el.removeEventListener('mouseup', onSelectMouseUp)
    el.removeEventListener('mousedown', onClearMouseDown)
    el.removeEventListener('mousemove', onClearMouseMove)
    el.removeEventListener('mouseup', onClearMouseUp)
    overlay.remove()
    rangeTooltip.remove()
    tooltip.remove()
    chart.remove()
  }

  return { render, resize, dispose }
}

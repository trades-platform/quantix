/**
 * ECharts option builder — translates API chart-data response into a
 * complete ECharts option object.  Mirrors the layout logic from
 * backend/plotting/renderers/pyecharts.py but emits native ECharts
 * configuration instead of pyecharts calls.
 */

// --- Theme colour constants ---
const THEMES = {
  dark: {
    bg: '#131722',
    text: '#d1d4dc',
    grid: '#2B2B43',
    up: '#26a69a',
    down: '#ef5350',
  },
  light: {
    bg: 'transparent',
    text: '#374151',
    grid: '#F3F4F6',
    up: '#EF4444',
    down: '#10B981',
  },
}

/**
 * Build a complete ECharts option object from API response data.
 *
 * @param {Array}  ohlcv       – [{timestamp, open, high, low, close, volume}, ...]
 * @param {Array}  indicators  – [{name, pane, kind, color, data}, ...]
 * @param {Array}  trades      – [{side, price, timestamp, ...}, ...]
 * @param {Object} opts        – optional overrides: {height, darkMode}
 * @returns {Object} ECharts option
 */
export function buildEChartsOption(ohlcv, indicators, trades, opts = {}) {
  if (!ohlcv || ohlcv.length === 0) {
    return {}
  }

  const themeName = opts.darkMode !== false ? 'dark' : 'light'
  const COLORS = THEMES[themeName]
  const timestamps = ohlcv.map((d) => d.timestamp)

  // Candlestick data: [open, close, low, high]
  const candleData = ohlcv.map((d) => [d.open, d.close, d.low, d.high])

  // Close prices array for volume colouring
  const closes = ohlcv.map((d) => d.close)

  // --- Group indicators by pane ---
  const paneMap = new Map()
  for (const ind of indicators) {
    const pane = ind.pane || 'main'
    if (!paneMap.has(pane)) {
      paneMap.set(pane, [])
    }
    paneMap.get(pane).push(ind)
  }

  // --- Pane order: main first, volume second, rest alphabetically ---
  const orderedPanes = []
  if (paneMap.has('main')) {
    orderedPanes.push('main')
  }
  if (paneMap.has('volume')) {
    orderedPanes.push('volume')
  }
  const remaining = [...paneMap.keys()]
    .filter((p) => !orderedPanes.includes(p))
    .sort()
  orderedPanes.push(...remaining)

  const nPanes = orderedPanes.length

  // --- Grid height allocation ---
  const totalHeight = 90 // usable percentage (leave room for dataZoom)
  const mainRatio = nPanes > 1 ? 0.50 : 0.90
  const mainPct = Math.floor(totalHeight * mainRatio)
  const subPct = nPanes > 1 ? Math.floor((totalHeight - mainPct) / (nPanes - 1)) : 0

  const grids = []
  const xAxes = []
  const yAxes = []
  const seriesList = []
  let currentTop = 5

  for (let paneIdx = 0; paneIdx < nPanes; paneIdx++) {
    const paneName = orderedPanes[paneIdx]
    const h = paneIdx === 0 ? mainPct : subPct
    const bottom = 100 - currentTop - h

    grids.push({
      left: '8%',
      right: '3%',
      top: `${currentTop}%`,
      bottom: `${bottom}%`,
    })

    xAxes.push({
      type: 'category',
      data: timestamps,
      gridIndex: paneIdx,
      scale: true,
      boundaryGap: paneName === 'volume',
      axisLine: { onZero: false },
      axisTick: { show: paneIdx === 0 },
      splitLine: { show: false },
      axisLabel: {
        show: paneIdx === 0,
        color: COLORS.text,
      },
      min: 'dataMin',
      max: 'dataMax',
    })

    yAxes.push({
      scale: true,
      gridIndex: paneIdx,
      splitLine: { lineStyle: { color: COLORS.grid } },
      axisLabel: { color: COLORS.text },
    })

    currentTop += h + 3
  }

  // --- Build series per pane ---
  for (let paneIdx = 0; paneIdx < nPanes; paneIdx++) {
    const paneName = orderedPanes[paneIdx]
    const paneIndicators = paneMap.get(paneName) || []

    if (paneName === 'main') {
      // Candlestick series
      seriesList.push({
        name: 'Price',
        type: 'candlestick',
        xAxisIndex: paneIdx,
        yAxisIndex: paneIdx,
        data: candleData,
        itemStyle: {
          color: COLORS.up,
          color0: COLORS.down,
          borderColor: COLORS.up,
          borderColor0: COLORS.down,
        },
      })

      // Overlay indicators on main pane
      for (const ind of paneIndicators) {
        if (ind.kind === 'line' && ind.data && ind.data.type === 'scalar') {
          seriesList.push({
            name: ind.name,
            type: 'line',
            xAxisIndex: paneIdx,
            yAxisIndex: paneIdx,
            data: ind.data.values,
            smooth: true,
            symbol: 'none',
            lineStyle: { width: 1, color: ind.color || '#F44336' },
            itemStyle: { color: ind.color || '#F44336' },
          })
        } else if (ind.kind === 'band' && ind.data && ind.data.type === 'band') {
          // Band indicator: render each sub-series as a separate line
          const bandParts = []
          if (ind.data.upper) bandParts.push({ key: 'upper', values: ind.data.upper, dashed: true })
          if (ind.data.middle) bandParts.push({ key: 'middle', values: ind.data.middle, dashed: false })
          if (ind.data.lower) bandParts.push({ key: 'lower', values: ind.data.lower, dashed: true })
          if (ind.data.extra) {
            for (const [k, v] of Object.entries(ind.data.extra)) {
              bandParts.push({ key: k, values: v, dashed: false })
            }
          }

          for (const part of bandParts) {
            seriesList.push({
              name: `${ind.name}-${part.key}`,
              type: 'line',
              xAxisIndex: paneIdx,
              yAxisIndex: paneIdx,
              data: part.values,
              smooth: true,
              symbol: 'none',
              lineStyle: {
                width: part.key === 'middle' ? 2 : 1,
                type: part.dashed ? 'dashed' : 'solid',
                color: ind.color || '#2196F3',
              },
              itemStyle: { color: ind.color || '#2196F3' },
            })
          }
        }
      }

      // Trade markers
      if (trades && trades.length > 0) {
        const tsToIdx = new Map()
        for (let i = 0; i < timestamps.length; i++) {
          tsToIdx.set(timestamps[i], i)
        }

        const markPointData = []
        for (const t of trades.slice(0, 100)) {
          const idx = tsToIdx.get(t.timestamp)
          if (idx === undefined) continue
          if (t.side === 'buy') {
            markPointData.push({
              coord: [idx, t.price],
              symbol: 'triangle',
              symbolSize: 10,
              itemStyle: { color: COLORS.down },
            })
          } else {
            markPointData.push({
              coord: [idx, t.price],
              symbol: 'path://M0,0L10,0L5,10Z', // inverted triangle
              symbolSize: 10,
              itemStyle: { color: COLORS.up },
            })
          }
        }

        if (markPointData.length > 0) {
          seriesList.push({
            name: 'Trades',
            type: 'line',
            xAxisIndex: paneIdx,
            yAxisIndex: paneIdx,
            data: new Array(timestamps.length).fill(null),
            symbol: 'none',
            lineStyle: { width: 0 },
            markPoint: {
              data: markPointData,
              animation: false,
            },
          })
        }
      }
    } else if (paneName === 'volume') {
      // Volume bars coloured by price direction
      let volValues = ohlcv.map((d) => d.volume)
      for (const ind of paneIndicators) {
        if (ind.data && ind.data.type === 'scalar' && ind.data.values && ind.data.values.length === ohlcv.length) {
          volValues = ind.data.values
          break
        }
      }

      seriesList.push({
        name: 'Volume',
        type: 'bar',
        xAxisIndex: paneIdx,
        yAxisIndex: paneIdx,
        data: volValues,
        itemStyle: {
          color: (params) => {
            const i = params.dataIndex
            if (i === 0 || !closes[i] || !closes[i - 1]) return COLORS.up
            return closes[i] >= closes[i - 1] ? COLORS.up : COLORS.down
          },
        },
      })
    } else {
      // Generic sub-pane (MACD, RSI, KDJ, ATR, equity, drawdown, etc.)
      for (const ind of paneIndicators) {
        if (ind.kind === 'histogram' && ind.data && ind.data.type === 'scalar') {
          seriesList.push({
            name: ind.name,
            type: 'bar',
            xAxisIndex: paneIdx,
            yAxisIndex: paneIdx,
            data: ind.data.values,
            itemStyle: {
              color: (params) => {
                const v = params.value
                return v != null && v >= 0 ? COLORS.up : COLORS.down
              },
            },
          })
        } else if (ind.kind === 'line' && ind.data && ind.data.type === 'scalar') {
          seriesList.push({
            name: ind.name,
            type: 'line',
            xAxisIndex: paneIdx,
            yAxisIndex: paneIdx,
            data: ind.data.values,
            smooth: true,
            symbol: 'none',
            lineStyle: { width: 1, color: ind.color || '#999' },
            itemStyle: { color: ind.color || '#999' },
          })
        } else if (ind.data && ind.data.type === 'band') {
          // Render band sub-series
          const bandParts = []
          if (ind.data.upper) bandParts.push({ key: 'upper', values: ind.data.upper })
          if (ind.data.middle) bandParts.push({ key: 'middle', values: ind.data.middle })
          if (ind.data.lower) bandParts.push({ key: 'lower', values: ind.data.lower })
          if (ind.data.extra) {
            for (const [k, v] of Object.entries(ind.data.extra)) {
              bandParts.push({ key: k, values: v })
            }
          }

          for (const part of bandParts) {
            // Use bar for histogram-like sub-keys (e.g. MACD histogram), line otherwise
            const isHistogramLike = part.key === 'histogram'
            // MACD colour overrides: DIF = red, DEA = tawny/golden-rod
            const isMacd = ind.name && ind.name.toUpperCase().startsWith('MACD')
            let lineColor = ind.color || '#999'
            if (!isHistogramLike && isMacd) {
              if (part.key === 'dif') lineColor = '#FF0000'
              if (part.key === 'dea') lineColor = '#DAA520'
            }
            seriesList.push({
              name: `${ind.name}-${part.key}`,
              type: isHistogramLike ? 'bar' : 'line',
              xAxisIndex: paneIdx,
              yAxisIndex: paneIdx,
              data: part.values,
              ...(isHistogramLike
                ? {
                    itemStyle: {
                      color: (params) => {
                        const v = params.value
                        return v != null && v >= 0 ? COLORS.up : COLORS.down
                      },
                    },
                  }
                : {
                    smooth: true,
                    symbol: 'none',
                    lineStyle: { width: 1, color: lineColor },
                    itemStyle: { color: lineColor },
                  }),
            })
          }
        }
      }
    }
  }

  // --- Shared dataZoom across all xAxes ---
  const xaxisIndices = Array.from({ length: nPanes }, (_, i) => i)
  const dataZoom = [
    {
      type: 'inside',
      xAxisIndex: xaxisIndices,
    },
  ]

  // Filter legend: exclude Price, Trades, Volume, and MACD sub-keys (dif/dea/histogram)
  const legendNames = seriesList
    .map((s) => s.name)
    .filter((n) => n && n !== 'Trades' && n !== 'Price' && n !== 'Volume' && !n.startsWith('MACD-'))

  // --- Assemble option ---
  return {
    animation: false,
    backgroundColor: COLORS.bg,
    textStyle: { color: COLORS.text },
    legend: {
      data: legendNames,
      top: 10,
      textStyle: { color: COLORS.text },
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      backgroundColor: themeName === 'dark' ? 'rgba(19,23,34,0.96)' : 'rgba(255,255,255,0.96)',
      borderColor: themeName === 'dark' ? '#2B2B43' : '#E5E7EB',
      textStyle: { color: themeName === 'dark' ? '#d1d4dc' : '#1F2937' },
      extraCssText: 'box-shadow: 0 2px 8px rgba(0,0,0,0.08);',
      formatter: (params) => {
        if (!params || params.length === 0) return ''
        const idx = params[0].dataIndex
        const bar = ohlcv[idx]
        if (!bar) return ''
        let html = `<div>时间: ${bar.timestamp}</div>`
        html += `<div>开盘: ${Number(bar.open).toFixed(2)}</div>`
        html += `<div>收盘: ${Number(bar.close).toFixed(2)}</div>`
        html += `<div>最高: ${Number(bar.high).toFixed(2)}</div>`
        html += `<div>最低: ${Number(bar.low).toFixed(2)}</div>`
        html += `<div>成交量: ${Number(bar.volume).toLocaleString()}</div>`
        // Append indicator values
        for (const p of params) {
          if (p.seriesName === 'Price' || p.seriesName === 'Trades' || p.seriesName === 'Volume') continue
          const val = p.value != null ? Number(p.value).toFixed(2) : '-'
          html += `<div>${p.seriesName}: ${val}</div>`
        }
        return html
      },
    },
    axisPointer: {
      link: [{ xAxisIndex: 'all' }],
      lineStyle: { color: '#9CA3AF' },
      label: { color: themeName === 'dark' ? '#d1d4dc' : '#374151', backgroundColor: themeName === 'dark' ? 'rgba(19,23,34,0.9)' : 'rgba(255,255,255,0.9)' },
    },
    grid: grids,
    xAxis: xAxes,
    yAxis: yAxes,
    dataZoom,
    series: seriesList,
  }
}

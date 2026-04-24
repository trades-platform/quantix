"""lightweight-charts renderer — HTML via CDN JS, optional pywebview"""

from __future__ import annotations

import json
import math
import re
from collections import defaultdict

import pandas as pd
from typing import TYPE_CHECKING

from backend.plotting.renderers import register

if TYPE_CHECKING:
    from backend.plotting.types import IndicatorSeries, PlotConfig

from backend.plotting.types import BandSeries, MAIN, ScalarSeries, SeriesKind, VOLUME


class LightweightChartsRenderer:
    """Renders charts using TradingView lightweight-charts via CDN JS."""

    def render(
        self,
        ohlcv_df: pd.DataFrame,
        indicators: list[IndicatorSeries],
        trades: list[dict],
        config: PlotConfig,
    ) -> RenderResult:
        timestamps = ohlcv_df["timestamp"].astype(str).tolist()

        # Build OHLCV data for lightweight-charts
        ohlcv_records = ohlcv_df[["timestamp", "open", "high", "low", "close"]].rename(
            columns={"timestamp": "time"}
        ).to_dict(orient="records")

        # Group indicators by pane
        panes: dict[str, list[IndicatorSeries]] = defaultdict(list)
        for ind in indicators:
            panes[ind.pane].append(ind)

        bg = "#131722" if config.dark_mode else "#ffffff"
        text_color = "#d1d4dc" if config.dark_mode else "#333333"
        grid_color = "#2B2B43" if config.dark_mode else "#e0e0e0"

        js_parts = []
        js_parts.append(f"""
const chart = LightweightCharts.createChart(document.getElementById('chart'), {{
    width: {config.width},
    height: {config.height},
    layout: {{ background: {{ color: '{bg}' }}, textColor: '{text_color}' }},
    grid: {{ vertLines: {{ color: '{grid_color}' }}, horzLines: {{ color: '{grid_color}' }} }},
    crosshair: {{ mode: LightweightCharts.CrosshairMode.Normal }},
    timeScale: {{ timeVisible: true, secondsVisible: false }},
}});

const candleSeries = chart.addCandlestickSeries({{
    upColor: '#26a69a', downColor: '#ef5350',
    borderUpColor: '#26a69a', borderDownColor: '#ef5350',
    wickUpColor: '#26a69a', wickDownColor: '#ef5350',
}});
candleSeries.setData({json.dumps(ohlcv_records, default=str)});
""")

        # Main pane overlays
        for ind in panes.get(MAIN, []):
            if ind.kind == SeriesKind.LINE and isinstance(ind.data, ScalarSeries):
                color = ind.color or "#F44336"
                data = [{"time": timestamps[i], "value": v} for i, v in enumerate(ind.data.data)]
                js_parts.append(f"""
const {self._js_id(ind.name)}_series = chart.addLineSeries({{
    color: '{color}', lineWidth: 1, priceLineVisible: false, lastValueVisible: false,
}});
{self._js_id(ind.name)}_series.setData({json.dumps(data, default=str)});
""")

            elif ind.kind == SeriesKind.BAND and isinstance(ind.data, BandSeries):
                series_map = {}
                if ind.data.upper:
                    series_map["upper"] = ind.data.upper
                if ind.data.middle:
                    series_map["middle"] = ind.data.middle
                if ind.data.lower:
                    series_map["lower"] = ind.data.lower
                series_map.update(ind.data.extra)

                band_colors = {"upper": "#78909C", "middle": ind.color or "#2196F3", "lower": "#78909C"}
                for sname, values in series_map.items():
                    color = band_colors.get(sname, ind.color or "#999")
                    line_style = "2" if sname != "middle" else "0"
                    data = []
                    for i, v in enumerate(values):
                        if v is None or (isinstance(v, float) and math.isnan(v)):
                            continue
                        ts = timestamps[i] if i < len(timestamps) else str(i)
                        data.append({"time": ts, "value": v})
                    js_parts.append(f"""
const {self._js_id(ind.name)}_{sname} = chart.addLineSeries({{
    color: '{color}', lineWidth: 1, lineStyle: {line_style},
    priceLineVisible: false, lastValueVisible: false,
}});
{self._js_id(ind.name)}_{sname}.setData({json.dumps(data, default=str)});
""")

        # Trade markers
        if config.show_trades and trades:
            markers = []
            for t in trades:
                ts = t.get("timestamp", "")
                price = t.get("price", 0)
                side = t.get("side", "")
                if side == "buy":
                    markers.append({
                        "time": ts, "price": price,
                        "shape": "arrowUp", "color": "#ef5350",
                        "text": "B",
                    })
                elif side == "sell":
                    markers.append({
                        "time": ts, "price": price,
                        "shape": "arrowDown", "color": "#26a69a",
                        "text": "S",
                    })
            if markers:
                js_parts.append(f"""
candleSeries.setMarkers({json.dumps(markers[:200], default=str)});
""")

        # Volume pane
        if VOLUME in panes:
            vol_data = [0.0] * len(timestamps)
            for ind in panes[VOLUME]:
                if isinstance(ind.data, ScalarSeries):
                    vol_data = ind.data.data
                    break
            records = []
            for i, v in enumerate(vol_data):
                if pd.isna(v):
                    continue
                ts = timestamps[i] if i < len(timestamps) else str(i)
                color = "#26a69a"
                if i > 0 and i < len(ohlcv_df):
                    curr_close = ohlcv_df.iloc[i]["close"]
                    prev_close = ohlcv_df.iloc[i - 1]["close"]
                    if curr_close < prev_close:
                        color = "#ef5350"
                records.append({"time": ts, "value": v, "color": color})
            js_parts.append(f"""
const volumeSeries = chart.addHistogramSeries({{
    priceFormat: {{ type: 'volume' }},
    priceScaleId: 'volume',
}});
chart.priceScale('volume').applyOptions({{
    scaleMargins: {{ top: 0.8, bottom: 0 }},
}});
volumeSeries.setData({json.dumps(records, default=str)});
""")

        # Generic indicator panes (MACD, RSI, KDJ, ATR, equity, drawdown)
        indicator_panes = [p for p in panes if p not in (MAIN, VOLUME)]
        n_ind = len(indicator_panes)
        for pane_idx, pane_name in enumerate(indicator_panes):
            slot = 0.55 / max(n_ind, 1)
            margin_top = 0.05 + pane_idx * slot
            margin_bottom = 1.0 - margin_top - slot
            scale_id = f"pane_{pane_name}"

            for ind in panes[pane_name]:
                if isinstance(ind.data, ScalarSeries):
                    data = []
                    for i, v in enumerate(ind.data.data):
                        if v is None or (isinstance(v, float) and math.isnan(v)):
                            continue
                        ts = timestamps[i] if i < len(timestamps) else str(i)
                        data.append({"time": ts, "value": v})
                    color = ind.color or "#999"
                    is_histogram = ind.kind == SeriesKind.HISTOGRAM
                    series_type = "addHistogramSeries" if is_histogram else "addLineSeries"

                    js_parts.append(f"""
const {self._js_id(ind.name)} = chart.{series_type}({{
    color: '{color}', lineWidth: 1,
    priceLineVisible: false, lastValueVisible: false,
    priceScaleId: '{scale_id}',
}});
chart.priceScale('{scale_id}').applyOptions({{
    scaleMargins: {{ top: {margin_top}, bottom: {margin_bottom} }},
}});
{self._js_id(ind.name)}.setData({json.dumps(data, default=str)});
""")

                elif isinstance(ind.data, BandSeries):
                    series_map = {}
                    if ind.data.extra:
                        series_map = dict(ind.data.extra)
                    elif ind.data.upper:
                        series_map = {"upper": ind.data.upper, "middle": ind.data.middle, "lower": ind.data.lower}

                    sub_colors = ["#2196F3", "#FF9800", "#AB47BC", "#26a69a", "#ef5350"]
                    for si, (sname, values) in enumerate(series_map.items()):
                        color = ind.color or sub_colors[si % len(sub_colors)]
                        data = []
                        for i, v in enumerate(values):
                            if v is None or (isinstance(v, float) and math.isnan(v)):
                                continue
                            ts = timestamps[i] if i < len(timestamps) else str(i)
                            data.append({"time": ts, "value": v})
                        js_parts.append(f"""
const {self._js_id(ind.name)}_{sname} = chart.addLineSeries({{
    color: '{color}', lineWidth: 1,
    priceLineVisible: false, lastValueVisible: false,
    priceScaleId: '{scale_id}',
}});
chart.priceScale('{scale_id}').applyOptions({{
    scaleMargins: {{ top: {margin_top}, bottom: {margin_bottom} }},
}});
{self._js_id(ind.name)}_{sname}.setData({json.dumps(data, default=str)});
""")

        js_code = "\n".join(js_parts)

        html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<script src="https://unpkg.com/lightweight-charts@4.2.0/dist/lightweight-charts.standalone.production.js"></script>
</head>
<body style="margin:0; background:{bg};">
<div id="chart"></div>
<script>
{js_code}
chart.timeScale().fitContent();
</script>
</body>
</html>"""
        from backend.plotting.renderers.base import RenderResult
        return RenderResult(html=html)

    def save(self, result: RenderResult, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            f.write(result.html)
        result.filepath = path

    def show(self, result: RenderResult) -> None:
        """Open chart in a native desktop window via pywebview."""
        import tempfile
        import webview

        tmp = tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w")
        tmp.write(result.html)
        tmp.close()
        webview.create_window("Quantix Chart", f"file://{tmp.name}", width=1200, height=800)
        webview.start()

    @staticmethod
    def _js_id(name: str) -> str:
        return re.sub(r"[^a-zA-Z0-9_]", "_", name)

register("lightweight", LightweightChartsRenderer)

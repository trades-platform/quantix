"""pyecharts renderer — standalone HTML output"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import TYPE_CHECKING

from backend.plotting.renderers import register

if TYPE_CHECKING:
    import pandas as pd
    from backend.plotting.types import IndicatorSeries, PlotConfig

from backend.plotting.types import BandSeries, MAIN, ScalarSeries, SeriesKind, VOLUME


class PyEchartsRenderer:
    """Renders charts using pyecharts -> self-contained HTML."""

    def render(
        self,
        ohlcv_df: pd.DataFrame,
        indicators: list[IndicatorSeries],
        trades: list[dict],
        config: PlotConfig,
    ) -> RenderResult:
        from pyecharts import options as opts
        from pyecharts.charts import Bar, Grid, Kline, Line

        timestamps = ohlcv_df["timestamp"].astype(str).tolist()
        ohlcv = ohlcv_df[["open", "close", "low", "high"]].values.tolist()

        # Group indicators by pane
        panes: dict[str, list[IndicatorSeries]] = defaultdict(list)
        for ind in indicators:
            panes[ind.pane].append(ind)

        # Determine pane order: main first, then volume, then indicator panes
        ordered_panes: list[str] = [MAIN]
        if VOLUME in panes:
            ordered_panes.append(VOLUME)
        for p in panes:
            if p not in ordered_panes:
                ordered_panes.append(p)

        n_panes = len(ordered_panes)
        # Height allocation: main gets more space
        total_height = config.height
        main_h_ratio = 0.5 if n_panes > 1 else 0.9
        main_h = int(total_height * main_h_ratio)
        sub_h = int((total_height - main_h) / max(n_panes - 1, 1)) if n_panes > 1 else 0

        pane_charts: dict[int, list] = {}  # pane_idx -> list of charts
        for pane_idx, pane_name in enumerate(ordered_panes):
            yaxis_index = pane_idx

            if pane_name == MAIN:
                chart = Kline()
                chart.add_xaxis(timestamps)
                chart.add_yaxis(
                    series_name="Price",
                    y_axis=ohlcv,
                    itemstyle_opts=opts.ItemStyleOpts(
                        color="#26a69a" if config.dark_mode else "#ef5350",
                        color0="#ef5350" if config.dark_mode else "#26a69a",
                        border_color="#26a69a" if config.dark_mode else "#ef5350",
                        border_color0="#ef5350" if config.dark_mode else "#26a69a",
                    ),
                )

                # Overlay LINE indicators (MA, EMA) on main pane
                for ind in panes.get(MAIN, []):
                    if ind.kind == SeriesKind.LINE and isinstance(ind.data, ScalarSeries):
                        line = Line()
                        line.add_xaxis(timestamps)
                        line.add_yaxis(
                            series_name=ind.name,
                            y_axis=ind.data.data,
                            is_smooth=True,
                            linestyle_opts=opts.LineStyleOpts(width=1),
                            label_opts=opts.LabelOpts(is_show=False),
                            symbol_size=0,
                            itemstyle_opts=opts.ItemStyleOpts(color=ind.color or "#F44336"),
                            yaxis_index=yaxis_index,
                            xaxis_index=pane_idx,
                        )
                        chart.overlap(line)

                    elif ind.kind == SeriesKind.BAND and isinstance(ind.data, BandSeries):
                        # Collect all sub-series: named fields first, then extra
                        series_items = []
                        for series_name in ("upper", "middle", "lower"):
                            values = getattr(ind.data, series_name, None)
                            if values is not None:
                                series_items.append((series_name, values))
                        for sname, values in ind.data.extra.items():
                            series_items.append((sname, values))

                        for series_name, values in series_items:
                            if values is None:
                                continue
                            line = Line()
                            line.add_xaxis(timestamps)
                            line.add_yaxis(
                                series_name=f"{ind.name}-{series_name}",
                                y_axis=values,
                                is_smooth=True,
                                linestyle_opts=opts.LineStyleOpts(
                                    width=1 if series_name != "middle" else 2,
                                    type_="dashed" if series_name != "middle" else "solid",
                                ),
                                label_opts=opts.LabelOpts(is_show=False),
                                symbol_size=0,
                                itemstyle_opts=opts.ItemStyleOpts(color=ind.color or "#2196F3"),
                                yaxis_index=yaxis_index,
                                xaxis_index=pane_idx,
                            )
                            chart.overlap(line)

                # Trade markers using coord (data index) for reliable positioning
                if config.show_trades and trades:
                    ts_to_idx = {ts: i for i, ts in enumerate(timestamps)}
                    buy_items, sell_items = [], []
                    for t in trades[:100]:
                        ts = t.get("timestamp", "")
                        price = t.get("price", 0)
                        idx = ts_to_idx.get(ts)
                        if idx is None:
                            continue
                        if t.get("side") == "buy":
                            buy_items.append(opts.MarkPointItem(
                                coord=[idx, price], symbol="triangle",
                                symbol_size=10, itemstyle_opts=opts.ItemStyleOpts(color="#ef5350"),
                            ))
                        else:
                            sell_items.append(opts.MarkPointItem(
                                coord=[idx, price], symbol="triangle",
                                symbol_rotate=180, symbol_size=10,
                                itemstyle_opts=opts.ItemStyleOpts(color="#26a69a"),
                            ))

                    if buy_items or sell_items:
                        mark_point_data = buy_items + sell_items
                        mark_line = Line()
                        mark_line.add_xaxis(timestamps)
                        mark_line.add_yaxis(
                            series_name="Trades",
                            y_axis=[None] * len(timestamps),
                            yaxis_index=yaxis_index,
                            xaxis_index=pane_idx,
                            markpoint_opts=opts.MarkPointOpts(data=mark_point_data),
                        )
                        chart.overlap(mark_line)

                pane_charts.setdefault(pane_idx, []).append(chart)

            elif pane_name == VOLUME:
                vol_data = [0.0] * len(timestamps)
                for ind in panes.get(VOLUME, []):
                    if isinstance(ind.data, ScalarSeries):
                        vol_data = ind.data.data
                        break

                # Build per-bar color list based on price direction
                from pyecharts.commons.utils import JsCode
                up_color = "#26a69a" if config.dark_mode else "#ef5350"
                dn_color = "#ef5350" if config.dark_mode else "#26a69a"

                # Serialize close prices for JsCode to compare
                closes_json = json.dumps([row[1] for row in ohlcv])  # ohlcv=[open,close,low,high]

                bar = Bar()
                bar.add_xaxis(timestamps)
                bar.add_yaxis(
                    series_name="Volume",
                    y_axis=vol_data,
                    xaxis_index=pane_idx,
                    yaxis_index=yaxis_index,
                    label_opts=opts.LabelOpts(is_show=False),
                )
                bar.set_series_opts(
                    itemstyle_opts=opts.ItemStyleOpts(
                        color=JsCode(
                            f"function(params) {{"
                            f"  var closes = {closes_json};"
                            f"  return params.dataIndex === 0 || closes[params.dataIndex] >= closes[params.dataIndex - 1]"
                            f"    ? '{up_color}' : '{dn_color}';"
                            f" }}"
                        )
                    )
                )
                pane_charts.setdefault(pane_idx, []).append(bar)

            elif pane_name == "equity":
                equity_data = [0.0] * len(timestamps)
                for ind in panes.get("equity", []):
                    if isinstance(ind.data, ScalarSeries):
                        equity_data = ind.data.data
                        break

                line = Line()
                line.add_xaxis(timestamps)
                line.add_yaxis(
                    series_name="Equity",
                    y_axis=equity_data,
                    is_smooth=True,
                    linestyle_opts=opts.LineStyleOpts(width=2),
                    label_opts=opts.LabelOpts(is_show=False),
                    symbol_size=0,
                    itemstyle_opts=opts.ItemStyleOpts(color="#26a69a"),
                    xaxis_index=pane_idx,
                    yaxis_index=yaxis_index,
                )
                pane_charts.setdefault(pane_idx, []).append(line)

            elif pane_name == "drawdown":
                dd_data = [0.0] * len(timestamps)
                for ind in panes.get("drawdown", []):
                    if isinstance(ind.data, ScalarSeries):
                        dd_data = ind.data.data
                        break

                bar = Bar()
                bar.add_xaxis(timestamps)
                bar.add_yaxis(
                    series_name="Drawdown",
                    y_axis=dd_data,
                    xaxis_index=pane_idx,
                    yaxis_index=yaxis_index,
                    label_opts=opts.LabelOpts(is_show=False),
                    itemstyle_opts=opts.ItemStyleOpts(color="#ef5350"),
                )
                pane_charts.setdefault(pane_idx, []).append(bar)

            else:
                # Generic indicator pane (MACD, RSI, KDJ, ATR, etc.)
                pane_indicators = panes.get(pane_name, [])
                if not pane_indicators:
                    continue

                # Render all indicators: histograms as Bar, lines/bands as Line
                has_hist = any(
                    ind.kind == SeriesKind.HISTOGRAM and isinstance(ind.data, ScalarSeries)
                    for ind in pane_indicators
                )
                bar = Bar() if has_hist else None
                line = Line()

                if bar is not None:
                    bar.add_xaxis(timestamps)
                line.add_xaxis(timestamps)

                has_data = False
                for ind in pane_indicators:
                    if ind.kind == SeriesKind.HISTOGRAM and isinstance(ind.data, ScalarSeries):
                        if bar is None:
                            bar = Bar()
                            bar.add_xaxis(timestamps)
                        bar.add_yaxis(
                            series_name=ind.name,
                            y_axis=ind.data.data,
                            xaxis_index=pane_idx,
                            yaxis_index=yaxis_index,
                            label_opts=opts.LabelOpts(is_show=False),
                            itemstyle_opts=opts.ItemStyleOpts(color=ind.color or "#616161"),
                        )
                        has_data = True
                    elif isinstance(ind.data, ScalarSeries):
                        line.add_yaxis(
                            series_name=ind.name,
                            y_axis=ind.data.data,
                            is_smooth=True,
                            label_opts=opts.LabelOpts(is_show=False),
                            symbol_size=0,
                            linestyle_opts=opts.LineStyleOpts(width=1),
                            itemstyle_opts=opts.ItemStyleOpts(color=ind.color or "#999"),
                            xaxis_index=pane_idx,
                            yaxis_index=yaxis_index,
                        )
                        has_data = True
                    elif isinstance(ind.data, BandSeries):
                        series_map = {}
                        if ind.data.upper:
                            series_map["upper"] = ind.data.upper
                        if ind.data.middle:
                            series_map["middle"] = ind.data.middle
                        if ind.data.lower:
                            series_map["lower"] = ind.data.lower
                        series_map.update(ind.data.extra)

                        for sname, values in series_map.items():
                            line.add_yaxis(
                                series_name=f"{ind.name}-{sname}",
                                y_axis=values,
                                is_smooth=True,
                                label_opts=opts.LabelOpts(is_show=False),
                                symbol_size=0,
                                linestyle_opts=opts.LineStyleOpts(width=1),
                                itemstyle_opts=opts.ItemStyleOpts(color=ind.color or "#999"),
                                xaxis_index=pane_idx,
                                yaxis_index=yaxis_index,
                            )
                            has_data = True

                if has_data:
                    if bar:
                        pane_charts.setdefault(pane_idx, []).append(bar)
                    pane_charts.setdefault(pane_idx, []).append(line)

        # Build Grid layout
        chart_pane_map: dict = {}
        all_charts = []
        for pi, clist in pane_charts.items():
            for c in clist:
                chart_pane_map[id(c)] = pi
                all_charts.append(c)
        if not all_charts:
            from backend.plotting.renderers.base import RenderResult
            return RenderResult(html="<html><body><p>No chart data</p></body></html>")

        grid = Grid(
            init_opts=opts.InitOpts(
                width=f"{config.width}px",
                height=f"{total_height}px",
                theme="dark" if config.dark_mode else "light",
                bg_color="#131722" if config.dark_mode else "#fff",
            )
        )

        # Calculate vertical positions per pane
        available = 90
        main_pct = min(int(main_h / total_height * 100), available - (n_panes - 1) * 3)
        sub_pct = (available - main_pct) // max(n_panes - 1, 1) if n_panes > 1 else 0

        positions: dict[int, tuple[int, int]] = {}
        current_top = 5
        for i, pane_name in enumerate(ordered_panes):
            h = main_pct if i == 0 else sub_pct
            positions[i] = (current_top, h)
            current_top += h + 3

        for chart in all_charts:
            pane_idx = chart_pane_map.get(id(chart), 0)
            t, h = positions[pane_idx]
            b = 100 - t - h
            grid.add(
                chart,
                grid_opts=opts.GridOpts(
                    pos_top=f"{t}%",
                    pos_bottom=f"{b}%",
                    pos_left="8%",
                    pos_right="3%",
                ),
            )

        # Shared dataZoom on all x-axes
        if n_panes > 1:
            xaxis_indices = list(range(n_panes))
            for chart in all_charts:
                chart.set_global_opts(
                    datazoom_opts=[
                        opts.DataZoomOpts(
                            is_show=True,
                            type_="inside",
                            xaxis_index=xaxis_indices,
                        ),
                    ],
                    axispointer_opts=opts.AxisPointerOpts(
                        is_show=True,
                        link=[{"xAxisIndex": "all"}],
                    ),
                )

        html = grid.render_embed()
        from backend.plotting.renderers.base import RenderResult
        return RenderResult(html=html)

    def save(self, result: RenderResult, path: str) -> None:
        full_html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
</head><body style="margin:0;">
{result.html}
</body></html>"""
        with open(path, "w", encoding="utf-8") as f:
            f.write(full_html)
        result.filepath = path


register("pyecharts", PyEchartsRenderer)

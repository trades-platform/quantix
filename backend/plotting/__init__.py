"""Quantix plotting — modular charting for backtest results"""

from backend.plotting.types import (
    BandSeries,
    IndicatorSeries,
    LayerSpec,
    MAIN,
    PlotConfig,
    ScalarSeries,
    SeriesData,
    SeriesKind,
    VOLUME,
)


class ChartBuilder:
    """Builds a chart from backtest results and K-line data."""

    def __init__(
        self,
        result: dict,
        kline_df: "pd.DataFrame",
        config: PlotConfig | None = None,
    ):
        self.result = result
        self.kline_df = kline_df
        self.config = config or PlotConfig()
        self._custom_indicators: list[IndicatorSeries] = []
        self._indicators_cache: list[IndicatorSeries] | None = None

    def add_indicator(self, indicator: IndicatorSeries) -> None:
        self._custom_indicators.append(indicator)
        self._indicators_cache = None

    def _build_indicators(self) -> list[IndicatorSeries]:
        from backend.plotting.compute import compute_equity_curve, compute_drawdown, compute_indicator

        series = list(self._custom_indicators)
        for spec in self.config.layers:
            ind = compute_indicator(self.kline_df, spec.indicator, spec.params)
            if spec.pane is not None:
                ind.pane = spec.pane
            if spec.kind is not None:
                ind.kind = spec.kind
            if spec.color is not None:
                ind.color = spec.color
            if spec.name:
                ind.name = spec.name
            series.append(ind)

        n_bars = len(self.kline_df)
        if self.config.show_equity_curve:
            series.append(compute_equity_curve(self.result.get("equity_curve", []), n_bars))

        if self.config.show_drawdown:
            series.append(compute_drawdown(self.result.get("equity_curve", []), n_bars))

        return series

    @property
    def indicators(self) -> list[IndicatorSeries]:
        if self._indicators_cache is None:
            self._indicators_cache = self._build_indicators()
        return self._indicators_cache

    def render(
        self,
        renderer_name: str = "pyecharts",
        output: str | None = None,
        show: bool = False,
    ) -> "RenderResult":
        try:
            import backend.plotting.renderers.pyecharts  # noqa: F401
        except ImportError:
            pass
        try:
            import backend.plotting.renderers.lightweight  # noqa: F401
        except ImportError:
            pass

        from backend.plotting.renderers import get_renderer

        renderer = get_renderer(renderer_name)
        result = renderer.render(
            ohlcv_df=self.kline_df,
            indicators=self.indicators,
            trades=self.result.get("trades", []),
            config=self.config,
        )

        if output:
            renderer.save(result, output)

        if show and hasattr(renderer, "show"):
            renderer.show(result)

        return result

"""Renderer protocol and result type"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import pandas as pd
    from backend.plotting.types import IndicatorSeries, PlotConfig


@dataclass
class RenderResult:
    html: str | None = None
    filepath: str | None = None


class ChartRenderer(Protocol):
    def render(
        self,
        ohlcv_df: pd.DataFrame,
        indicators: list[IndicatorSeries],
        trades: list[dict],
        config: PlotConfig,
    ) -> RenderResult: ...

    def save(self, result: RenderResult, path: str) -> None: ...

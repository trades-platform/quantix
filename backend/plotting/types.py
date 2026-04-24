"""绘图数据类型定义"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Union


# --- Pane constants (conventions, not constraints) ---

MAIN = "main"
VOLUME = "volume"


class SeriesKind(Enum):
    LINE = "line"
    HISTOGRAM = "histogram"
    BAND = "band"
    MARKERS = "markers"


# --- Typed series data ---

@dataclass
class ScalarSeries:
    data: list[float]


@dataclass
class BandSeries:
    upper: list[float] | None = None
    middle: list[float] | None = None
    lower: list[float] | None = None
    extra: dict[str, list[float]] = field(default_factory=dict)


SeriesData = Union[ScalarSeries, BandSeries]


@dataclass
class IndicatorSeries:
    name: str
    pane: str
    kind: SeriesKind
    data: SeriesData
    color: str | None = None


# --- Declarative config ---

@dataclass
class LayerSpec:
    indicator: str
    name: str
    kind: SeriesKind | None = None
    pane: str | None = None
    color: str | None = None
    params: dict = field(default_factory=dict)


@dataclass
class PlotConfig:
    title: str = ""
    width: int = 1200
    height: int = 700
    layers: list[LayerSpec] = field(default_factory=list)
    show_trades: bool = True
    show_equity_curve: bool = False
    show_drawdown: bool = False
    dark_mode: bool = True

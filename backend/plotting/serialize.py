"""Serialization helpers — convert plotting types to JSON-serializable dicts."""

from __future__ import annotations

import json
import math
from typing import Any

from backend.plotting.types import (
    BandSeries,
    IndicatorSeries,
    LayerSpec,
    PlotConfig,
    ScalarSeries,
    SeriesData,
    SeriesKind,
)


def _nan_to_none(value: Any) -> Any:
    """Convert NaN / Inf floats to None so they become JSON null."""
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def _clean_list(values: list[float]) -> list:
    """Return a copy of *values* with NaN/Inf replaced by None."""
    return [_nan_to_none(v) for v in values]


def _series_data_to_dict(data: SeriesData) -> dict:
    """Convert ScalarSeries or BandSeries to a JSON-serializable dict."""
    if isinstance(data, ScalarSeries):
        return {"type": "scalar", "values": _clean_list(data.data)}

    if isinstance(data, BandSeries):
        result: dict[str, Any] = {"type": "band"}
        if data.upper is not None:
            result["upper"] = _clean_list(data.upper)
        if data.middle is not None:
            result["middle"] = _clean_list(data.middle)
        if data.lower is not None:
            result["lower"] = _clean_list(data.lower)
        if data.extra:
            result["extra"] = {
                key: _clean_list(vals) for key, vals in data.extra.items()
            }
        return result

    # Fallback — should not happen with well-typed data
    return {"type": "unknown"}


def indicator_series_to_dict(ind: IndicatorSeries) -> dict:
    """Convert an IndicatorSeries to a JSON-serializable dict.

    Output shape::

        {
            "name": "MA(5)",
            "pane": "main",
            "kind": "line",          # SeriesKind enum value as string
            "color": "#F44336",
            "data": {"type": "scalar", "values": [...]}
        }

    For band series the *data* key contains upper/middle/lower/extra arrays.
    NaN floats are converted to ``None`` (JSON null).
    """
    return {
        "name": ind.name,
        "pane": ind.pane,
        "kind": ind.kind.value,
        "color": ind.color,
        "data": _series_data_to_dict(ind.data),
    }


# --- Default indicator layers (used when the frontend sends none) ---

DEFAULT_LAYERS = [
    {"indicator": "ma", "name": "MA(5)", "params": {"period": 5}, "color": "#F44336"},
    {"indicator": "ma", "name": "MA(20)", "params": {"period": 20}, "color": "#2196F3"},
    {"indicator": "volume", "name": "Volume", "pane": "volume"},
]


def _raw_to_layerspec(raw: dict) -> LayerSpec:
    kind = None
    if raw.get("kind"):
        try:
            kind = SeriesKind(raw["kind"])
        except ValueError:
            pass
    return LayerSpec(
        indicator=raw.get("indicator", ""),
        name=raw.get("name", ""),
        kind=kind,
        pane=raw.get("pane"),
        color=raw.get("color"),
        params=raw.get("params", {}),
    )


def plot_config_from_params(
    layers_json: str = "",
    show_trades: bool = True,
    show_equity_curve: bool = True,
    show_drawdown: bool = False,
) -> PlotConfig:
    """Parse frontend query params into a PlotConfig.

    *layers_json* is a JSON string encoding a list of LayerSpec dicts.
    If empty or invalid, the built-in defaults are used.
    """
    layers: list[LayerSpec] = []

    if layers_json:
        try:
            layers = [_raw_to_layerspec(raw) for raw in json.loads(layers_json)]
        except (json.JSONDecodeError, TypeError):
            layers = []

    if not layers:
        layers = [_raw_to_layerspec(d) for d in DEFAULT_LAYERS]

    return PlotConfig(
        layers=layers,
        show_trades=show_trades,
        show_equity_curve=show_equity_curve,
        show_drawdown=show_drawdown,
    )

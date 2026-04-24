"""Renderer registry"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.plotting.renderers.base import ChartRenderer

_BACKENDS: dict[str, type[ChartRenderer]] = {}


def register(name: str, cls: type[ChartRenderer]) -> None:
    _BACKENDS[name] = cls


def get_renderer(name: str) -> ChartRenderer:
    if name not in _BACKENDS:
        available = ", ".join(_BACKENDS) if _BACKENDS else "(none registered)"
        raise ValueError(f"Unknown renderer: {name!r}. Available: {available}")
    return _BACKENDS[name]()


def available_backends() -> list[str]:
    return list(_BACKENDS)

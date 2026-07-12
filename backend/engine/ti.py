"""统一技术指标计算引擎

基于 core-ti，作为全项目技术指标计算的**唯一真实源**。回测引擎
（``SymbolIndicators``）与图表绘制（``plotting.compute``）均通过这里的共享
``IndicatorEngine`` 计算，避免公式各写一份导致口径不一致。

使用纯 Python 的 ``pandas`` 后端，保证与依赖无关的确定性结果。
"""

from __future__ import annotations

from functools import lru_cache

import pandas as pd
from core_ti import IndicatorEngine
from core_ti.schema import resolve_output_names


@lru_cache(maxsize=1)
def get_engine() -> IndicatorEngine:
    """返回进程级共享的指标引擎（pandas 后端）。"""
    return IndicatorEngine(backend="pandas")


def output_names(name: str, params: dict) -> list[str]:
    """解析指标的输出列名。

    例：``output_names("sma", {"period": 20})`` -> ``["sma_20"]``。
    """
    meta = get_engine().get_indicator(name)
    return resolve_output_names(meta.outputs, params)


def ensure_columns(df: pd.DataFrame, name: str, params: dict) -> list[str]:
    """在 *df* 上原地补齐指标输出列（已存在则跳过），返回输出列名列表。

    直接修改传入的 DataFrame，适合对同一份数据反复取不同指标/参数的场景。
    """
    cols = output_names(name, params)
    if any(c not in df.columns for c in cols):
        getattr(get_engine().pipe(df), name)(**params).result()
    return cols


def compute(df: pd.DataFrame, name: str, params: dict) -> pd.DataFrame:
    """在 *df* 上计算指标，返回仅含该指标输出列的 DataFrame（保留原索引）。

    若 *df* 已包含目标列（例如经 :func:`compute_many` 预热），则直接复用、
    不再拷贝或重算；否则在副本上计算，不修改传入的 DataFrame。
    """
    cols = output_names(name, params)
    if all(c in df.columns for c in cols):
        return df[cols]
    out = getattr(get_engine().pipe(df.copy()), name)(**params).result()
    return out[cols]


def compute_many(df: pd.DataFrame, specs: list[tuple[str, dict]]) -> pd.DataFrame:
    """一次性批量计算多个指标，返回带全部输出列的 *df* 副本。

    只拷贝一次数据，并由 core-ti 在单个 DAG 内自动去重共享依赖（如多个指标
    共用的 EMA）。适合图表一次渲染多条指标叠加的场景。
    """
    work = df.copy()
    if specs:
        pipe = get_engine().pipe(work)
        for name, params in specs:
            pipe = getattr(pipe, name)(**params)
        pipe.result()
    return work


"""图表数据 API — 为前端 KlineChart 提供序列化后的 OHLCV + 指标数据"""

from __future__ import annotations

import json
import math
from datetime import date, datetime

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException

from backend.db import SessionLocal, get_market_data
from backend.models import Backtest, Trade
from backend.plotting import ChartBuilder
from backend.plotting.serialize import (
    indicator_series_to_dict,
    plot_config_from_params,
)

router = APIRouter(prefix="/backtests", tags=["charts"])


def _clean_value(v):
    """Convert numpy/pandas scalar to a JSON-safe Python value."""
    if v is None:
        return None
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        fv = float(v)
        return None if (math.isnan(fv) or math.isinf(fv)) else fv
    return v


def _ohlcv_to_dicts(df: pd.DataFrame) -> list[dict]:
    """Convert an OHLCV DataFrame to a list of JSON-serializable dicts."""
    records = df[["timestamp", "open", "high", "low", "close", "volume"]].to_dict(orient="records")
    for r in records:
        ts = r["timestamp"]
        if isinstance(ts, (pd.Timestamp, datetime)):
            r["timestamp"] = ts.isoformat()
        else:
            r["timestamp"] = str(ts)
        for key in ("open", "high", "low", "close", "volume"):
            r[key] = _clean_value(r[key])
    return records


def _trade_to_dict(t: Trade) -> dict:
    """Convert a Trade ORM object to a JSON-serializable dict."""
    ts = t.timestamp
    if isinstance(ts, datetime):
        ts_str = ts.isoformat()
    else:
        ts_str = str(ts)
    return {
        "id": t.id,
        "backtest_id": t.backtest_id,
        "symbol": t.symbol,
        "side": t.side,
        "price": float(t.price),
        "quantity": t.quantity,
        "timestamp": ts_str,
        "commission": float(t.commission) if t.commission is not None else None,
        "pnl": float(t.pnl) if t.pnl is not None else None,
    }


@router.get("/{backtest_id}/chart-data")
def get_chart_data(
    backtest_id: int,
    layers: str = "",
    show_trades: bool = True,
    show_equity_curve: bool = True,
    show_drawdown: bool = False,
    start_idx: int = 0,
    max_bars: int = 2000,
):
    """Return serialised OHLCV + indicator data for the frontend chart builder.

    Query parameters
    ----------------
    layers : str
        JSON-encoded list of LayerSpec dicts.  When empty the default
        layers (MA5, MA20, Volume) are used.
    show_trades : bool
        Whether to include trade markers in the response.
    show_equity_curve : bool
        Whether to include the equity curve overlay.
    show_drawdown : bool
        Whether to include the drawdown overlay.
    start_idx : int
        Zero-based bar index to start from (for pagination).
    max_bars : int
        Maximum number of bars to return.
    """
    # 1. Load backtest from DB
    with SessionLocal() as db:
        backtest = db.query(Backtest).filter(Backtest.id == backtest_id).first()
        if not backtest:
            raise HTTPException(status_code=404, detail="回测不存在")

        symbol = backtest.symbol
        start_date = backtest.start_date
        end_date = backtest.end_date
        equity_curve_raw = backtest.equity_curve

        # 2. Load trades
        db_trades = (
            db.query(Trade)
            .filter(Trade.backtest_id == backtest_id)
            .order_by(Trade.timestamp)
            .all()
        )

    # 3. Parse chart configuration
    config = plot_config_from_params(
        layers_json=layers,
        show_trades=show_trades,
        show_equity_curve=show_equity_curve,
        show_drawdown=show_drawdown,
    )

    # 4. Fetch kline data from LanceDB
    start_dt = datetime.combine(start_date, datetime.min.time()) if isinstance(start_date, date) else start_date
    end_dt = datetime.combine(end_date, datetime.min.time()) if isinstance(end_date, date) else end_date

    period = backtest.period or "1D"
    adjust = backtest.adjust or "hfq"

    data_dict = get_market_data(
        symbols=symbol,
        start_date=start_dt,
        end_date=end_dt,
        period=period,
        adjust=adjust,
    )

    kline_df = data_dict.get(symbol, pd.DataFrame())
    if kline_df.empty:
        raise HTTPException(status_code=400, detail=f"无 {symbol} 的K线数据")

    # 5. Build indicators via ChartBuilder
    equity_curve: list[float] = []
    if equity_curve_raw:
        try:
            parsed = json.loads(equity_curve_raw)
            if isinstance(parsed, list):
                for v in parsed:
                    if isinstance(v, (int, float)):
                        equity_curve.append(float(v))
                    elif isinstance(v, dict):
                        equity_curve.append(float(v.get("value", 0)))
        except (json.JSONDecodeError, TypeError, ValueError):
            equity_curve = []

    trades_raw = [_trade_to_dict(t) for t in db_trades]

    result = {
        "equity_curve": equity_curve,
        "trades": trades_raw,
    }

    builder = ChartBuilder(result=result, kline_df=kline_df, config=config)
    indicators = [indicator_series_to_dict(ind) for ind in builder.indicators]

    # 6. Apply pagination
    total_bars = len(kline_df)
    end_idx = min(start_idx + max_bars, total_bars)
    sliced_df = kline_df.iloc[start_idx:end_idx]

    # Slice indicator values to match the paginated window
    for ind_dict in indicators:
        data = ind_dict.get("data", {})
        if data.get("type") == "scalar":
            data["values"] = data["values"][start_idx:end_idx]
        elif data.get("type") == "band":
            for key in ("upper", "middle", "lower"):
                if key in data:
                    data[key] = data[key][start_idx:end_idx]
            if "extra" in data:
                for key in data["extra"]:
                    data["extra"][key] = data["extra"][key][start_idx:end_idx]

    # Filter trades to the visible window
    visible_trades = []
    if show_trades and trades_raw:
        ts_set = set()
        for ts in sliced_df["timestamp"].tolist():
            ts_set.add(str(ts) if not isinstance(ts, str) else ts)
        for t in trades_raw:
            if str(t["timestamp"]) in ts_set:
                visible_trades.append(t)

    ohlcv = _ohlcv_to_dicts(sliced_df)

    return {
        "symbol": symbol,
        "period": period,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "total_bars": total_bars,
        "start_idx": start_idx,
        "end_idx": end_idx,
        "ohlcv": ohlcv,
        "indicators": indicators,
        "trades": visible_trades,
    }

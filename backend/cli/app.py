"""Quantix CLI"""

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pandas as pd
import typer

from backend.models import Trade

app = typer.Typer(name="quantix", help="量化回测平台")


def _persist_trades(db, backtest_id: int, trades: list):
    for trade in trades:
        db_trade = Trade(
            backtest_id=backtest_id,
            symbol=trade["symbol"],
            side=trade["side"],
            price=Decimal(str(trade["price"])),
            quantity=trade["quantity"],
            timestamp=datetime.fromisoformat(trade["timestamp"]) if isinstance(trade["timestamp"], str) else trade["timestamp"],
            commission=Decimal(str(trade["commission"])) if trade.get("commission") is not None else None,
            pnl=Decimal(str(trade["pnl"])) if trade.get("pnl") is not None else None,
        )
        db.add(db_trade)


def _parse_period(period_str: str) -> int:
    """解析 K 线周期字符串"""
    import AmazingData as AD

    period_map = {
        "min1": AD.constant.Period.min1.value,
        "min5": AD.constant.Period.min5.value,
        "min15": AD.constant.Period.min15.value,
        "min30": AD.constant.Period.min30.value,
        "min60": AD.constant.Period.min60.value,
        "day": AD.constant.Period.day.value,
        "week": AD.constant.Period.week.value,
        "month": AD.constant.Period.month.value,
    }
    if period_str not in period_map:
        raise typer.BadParameter(f"不支持的周期: {period_str}，可选: {list(period_map.keys())}")
    return period_map[period_str]


def _resolve_target_symbols(raw_targets: str | list[str]) -> tuple[list[str], str]:
    from backend.db import SessionLocal, get_display_target, resolve_symbol_targets

    try:
        display_target = get_display_target(raw_targets)
        with SessionLocal() as db:
            symbols = resolve_symbol_targets(db, raw_targets)
        return symbols, display_target
    except (LookupError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)


def _fetch_symbols_from_provider(
    symbols: list[str],
    period_int: int,
    start_date: str | None,
    end_date: str | None,
    increment: bool,
) -> tuple[list[dict], list[dict]]:
    from backend.data import fetch_kline as data_fetch_kline

    success: list[dict] = []
    failed: list[dict] = []

    for i, symbol in enumerate(symbols, 1):
        typer.echo(f"[{i}/{len(symbols)}] 导入 {symbol}...")
        try:
            count = data_fetch_kline(symbol, period_int, start_date, end_date, increment)
            success.append({"symbol": symbol, "count": count})
        except Exception as exc:
            failed.append({"symbol": symbol, "error": str(exc)})
            typer.echo(f"  失败: {exc}", err=True)

    return success, failed


# 数据管理子命令
data_app = typer.Typer(name="data", help="数据管理")
app.add_typer(data_app, name="data")

# 标的池子命令
pool_app = typer.Typer(name="pool", help="标的池管理")
app.add_typer(pool_app, name="pool")


@app.command()
def serve(host: str = "0.0.0.0", port: int = 8000):
    """启动 API 服务"""
    import uvicorn

    uvicorn.run("backend.main:app", host=host, port=port, reload=False)


@app.command()
def initdb():
    """初始化数据库"""
    from backend.db.sqlite import init_db

    init_db()
    typer.echo("数据库初始化完成")


@data_app.command("import")
def import_kline_cmd(
    symbol: str = typer.Argument(..., help="标的代码，如 600000.SH"),
    file_path: Path = typer.Argument(..., help="CSV 文件路径", exists=True),
):
    """导入K线数据

    CSV 格式: timestamp,open,high,low,close,volume[,amount]
    """
    from backend.db import import_kline

    try:
        df = pd.read_csv(file_path)
        count = import_kline(symbol, df)
        typer.echo(f"成功导入 {count} 条数据")
    except Exception as e:
        typer.echo(f"导入失败: {e}", err=True)
        raise typer.Exit(1)


@data_app.command("list")
def list_symbols_cmd():
    """列出所有已有数据的标的"""
    from backend.db import SessionLocal
    from backend.models import Symbol

    with SessionLocal() as db:
        symbols = db.query(Symbol).order_by(Symbol.symbol).all()
        if not symbols:
            typer.echo("暂无数据")
        else:
            typer.echo(f"\n{'标的':<15} {'名称':<10} {'类型':<8} {'数据量':<10} {'最新时间'}")
            typer.echo("-" * 60)
            for s in symbols:
                name = s.name or "-"
                dtype = s.data_type or "-"
                latest = s.latest_timestamp.strftime("%Y-%m-%d %H:%M") if s.latest_timestamp else "-"
                typer.echo(f"{s.symbol:<15} {name:<10} {dtype:<8} {s.row_count:<10} {latest}")


@data_app.command("show")
def show_kline_cmd(
    symbol: str = typer.Argument(..., help="标的代码"),
    start_date: str | None = typer.Option(None, help="开始日期 YYYY-MM-DD"),
    end_date: str | None = typer.Option(None, help="结束日期 YYYY-MM-DD"),
    limit: int = typer.Option(10, help="显示行数"),
):
    """显示K线数据"""
    from backend.db.kline import _query_kline

    symbols, display_target = _resolve_target_symbols(symbol)
    if len(symbols) != 1:
        typer.echo(f"data show 仅支持单标的，当前 {display_target} 解析为 {', '.join(symbols)}", err=True)
        raise typer.Exit(1)

    target_symbol = symbols[0]
    start_dt = datetime.strptime(start_date, "%Y-%m-%d") if start_date else None
    end_dt = datetime.strptime(end_date, "%Y-%m-%d") if end_date else None

    data = _query_kline(target_symbol, start_dt, end_dt)

    if len(data) == 0:
        typer.echo(f"无 {target_symbol} 的数据")
        return

    typer.echo(f"\n{target_symbol} K线数据 (共 {len(data)} 条):\n")
    typer.echo(data.head(limit).to_string(index=False))


@data_app.command("fetch")
def fetch_kline_cmd(
    symbol: str = typer.Argument(..., help="标的代码或 @标的池，如 600000.SH / @etf_core"),
    period: str = typer.Option("min1", help="K线周期: min1/min5/min15/min30/min60/day/week/month"),
    start_date: str | None = typer.Option(None, help="开始日期 YYYY-MM-DD"),
    end_date: str | None = typer.Option(None, help="结束日期 YYYY-MM-DD"),
    increment: bool = typer.Option(False, help="增量导入（从最新数据时间到当前）"),
):
    """从 AmazingData 获取并导入K线数据"""
    period_int = _parse_period(period)
    symbols, display_target = _resolve_target_symbols(symbol)

    if len(symbols) > 1:
        typer.echo(f"{display_target} -> {', '.join(symbols)}")

    success, failed = _fetch_symbols_from_provider(symbols, period_int, start_date, end_date, increment)
    if failed:
        raise typer.Exit(1)

    count = sum(item["count"] for item in success)
    if increment:
        typer.echo(f"增量导入完成: {display_target} 新增 {count} 条数据")
    else:
        typer.echo(f"导入完成: {display_target} 共 {count} 条数据")


@data_app.command("fetch-all")
def fetch_all_cmd(
    data_type: str = typer.Option("both", help="数据类型: stock/etf/both"),
    period: str = typer.Option("min1", help="K线周期: min1/min5/min15/min30/min60/day/week/month"),
    start_date: str = typer.Option(..., help="开始日期 YYYY-MM-DD"),
    end_date: str = typer.Option(..., help="结束日期 YYYY-MM-DD"),
):
    """批量获取并导入所有股票/ETF的K线数据"""
    from backend.data import fetch_all as data_fetch_all

    period_int = _parse_period(period)

    valid_types = ["stock", "etf", "both"]
    if data_type not in valid_types:
        raise typer.BadParameter(f"无效类型: {data_type}，可选: {valid_types}")

    try:
        results = data_fetch_all(
            data_type,
            period_int,
            start_date,
            end_date,
        )

        success_count = len(results["success"])
        failed_count = len(results["failed"])

        typer.echo(f"\n批量导入完成:")
        typer.echo(f"  成功: {success_count}")
        typer.echo(f"  失败: {failed_count}")

        if results["failed"]:
            typer.echo("\n失败标的:")
            for item in results["failed"][:10]:
                typer.echo(f"  {item['symbol']}: {item['error']}")
            if len(results["failed"]) > 10:
                typer.echo(f"  ... 还有 {len(results['failed']) - 10} 个")

    except Exception as e:
        typer.echo(f"获取失败: {e}", err=True)
        raise typer.Exit(1)


@data_app.command("fetch-batch")
def fetch_batch_cmd(
    symbols: list[str] = typer.Argument(..., help="标的代码列表，如 600000.SH 000001.SZ"),
    period: str = typer.Option("min1", help="K线周期: min1/min5/min15/min30/min60/day/week/month"),
    start_date: str | None = typer.Option(None, help="开始日期 YYYY-MM-DD"),
    end_date: str | None = typer.Option(None, help="结束日期 YYYY-MM-DD"),
    increment: bool = typer.Option(False, help="增量导入（从最新数据时间到当前）"),
):
    """批量获取并导入指定标的的K线数据"""
    period_int = _parse_period(period)
    resolved_symbols, display_target = _resolve_target_symbols(symbols)
    if len(resolved_symbols) != len(symbols) or any(item.startswith("@") for item in symbols):
        typer.echo(f"{display_target} -> {', '.join(resolved_symbols)}")

    success, failed = _fetch_symbols_from_provider(resolved_symbols, period_int, start_date, end_date, increment)

    typer.echo(f"\n批量导入完成:")
    typer.echo(f"  成功: {len(success)}")
    typer.echo(f"  失败: {len(failed)}")

    if failed:
        typer.echo("\n失败标的:")
        for item in failed:
            typer.echo(f"  {item['symbol']}: {item['error']}")

    if failed:
        raise typer.Exit(1)


@pool_app.command("list")
def list_symbol_pools_cmd():
    """列出所有标的池"""
    from backend.db import SessionLocal, list_symbol_pools

    with SessionLocal() as db:
        pools = list_symbol_pools(db)

    if not pools:
        typer.echo("暂无标的池")
        return

    typer.echo(f"\n{'名称':<20} {'数量':<6} {'描述'}")
    typer.echo("-" * 80)
    for pool in pools:
        typer.echo(f"{pool.name:<20} {len(pool.symbols):<6} {pool.description or '-'}")


@pool_app.command("show")
def show_symbol_pool_cmd(
    name: str = typer.Argument(..., help="标的池名称"),
):
    """显示标的池详情"""
    from backend.db import SessionLocal, get_symbol_pool_by_name

    with SessionLocal() as db:
        pool = get_symbol_pool_by_name(db, name)

    if not pool:
        typer.echo("标的池不存在", err=True)
        raise typer.Exit(1)

    typer.echo(f"名称: {pool.name}")
    typer.echo(f"描述: {pool.description or '-'}")
    typer.echo(f"标的数: {len(pool.symbols)}")
    typer.echo(f"标的: {', '.join(pool.symbols)}")


@pool_app.command("create")
def create_symbol_pool_cmd(
    name: str = typer.Argument(..., help="标的池名称"),
    symbols: str = typer.Argument(..., help="标的代码，支持逗号分隔"),
    description: str = typer.Option("", "--description", "-d", help="标的池描述"),
):
    """创建标的池"""
    from backend.db import SessionLocal, create_symbol_pool

    with SessionLocal() as db:
        try:
            pool = create_symbol_pool(db, name, symbols, description)
        except ValueError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(1)

    typer.echo(f"已创建标的池 @{pool.name}: {', '.join(pool.symbols)}")


@pool_app.command("update")
def update_symbol_pool_cmd(
    name: str = typer.Argument(..., help="标的池名称"),
    new_name: str | None = typer.Option(None, "--new-name", help="新的标的池名称"),
    symbols: str | None = typer.Option(None, "--symbols", "-s", help="新的标的代码列表，支持逗号分隔"),
    description: str | None = typer.Option(None, "--description", "-d", help="新的描述，可传空字符串清空"),
):
    """更新标的池"""
    from backend.db import SessionLocal, get_symbol_pool_by_name, update_symbol_pool

    if new_name is None and symbols is None and description is None:
        typer.echo("至少提供一个更新项", err=True)
        raise typer.Exit(1)

    with SessionLocal() as db:
        pool = get_symbol_pool_by_name(db, name)
        if not pool:
            typer.echo("标的池不存在", err=True)
            raise typer.Exit(1)

        try:
            pool = update_symbol_pool(db, pool, name=new_name, symbols=symbols, description=description)
        except ValueError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(1)

    typer.echo(f"已更新标的池 @{pool.name}: {', '.join(pool.symbols)}")


@pool_app.command("delete")
def delete_symbol_pool_cmd(
    name: str = typer.Argument(..., help="标的池名称"),
    yes: bool = typer.Option(False, "--yes", "-y", help="不提示确认，直接删除"),
):
    """删除标的池"""
    from backend.db import SessionLocal, delete_symbol_pool, get_symbol_pool_by_name

    with SessionLocal() as db:
        pool = get_symbol_pool_by_name(db, name)
        if not pool:
            typer.echo("标的池不存在", err=True)
            raise typer.Exit(1)

        if not yes and not typer.confirm(f"确认删除标的池 @{pool.name} 吗？"):
            raise typer.Exit(1)

        delete_symbol_pool(db, pool)

    typer.echo(f"已删除标的池 @{name}")


# ---- Factor 命令 ----


@data_app.command("factor-fetch")
def fetch_factor_cmd(
    symbol: str = typer.Argument(..., help="标的代码，如 600000.SH"),
):
    """从 AmazingData 获取并导入后复权因子数据"""
    from backend.data import fetch_factor as data_fetch_factor

    try:
        count = data_fetch_factor(symbol)
        typer.echo(f"导入完成: {symbol} 压缩后 {count} 条因子数据")
    except Exception as e:
        typer.echo(f"获取失败: {e}", err=True)
        raise typer.Exit(1)


@data_app.command("factor-fetch-batch")
def fetch_factor_batch_cmd(
    symbols: list[str] = typer.Argument(..., help="标的代码列表"),
):
    """批量获取并导入指定标的的后复权因子数据"""
    from backend.data import fetch_factor_batch as data_fetch_factor_batch

    try:
        results = data_fetch_factor_batch(symbols)
        success_count = len(results["success"])
        failed_count = len(results["failed"])
        typer.echo(f"\n批量导入完成: 成功 {success_count}, 失败 {failed_count}")
        if results["failed"]:
            typer.echo("\n失败标的:")
            for item in results["failed"][:10]:
                typer.echo(f"  {item['symbol']}: {item['error']}")
            if len(results["failed"]) > 10:
                typer.echo(f"  ... 还有 {len(results['failed']) - 10} 个")
    except Exception as e:
        typer.echo(f"获取失败: {e}", err=True)
        raise typer.Exit(1)


@data_app.command("factor-fetch-all")
def fetch_factor_all_cmd(
    data_type: str = typer.Option("both", help="数据类型: stock/etf/both"),
):
    """批量获取所有股票/ETF的后复权因子数据"""
    from backend.data import fetch_factor_all as data_fetch_factor_all

    valid_types = ["stock", "etf", "both"]
    if data_type not in valid_types:
        raise typer.BadParameter(f"无效类型: {data_type}，可选: {valid_types}")

    try:
        results = data_fetch_factor_all(data_type)
        success_count = len(results["success"])
        failed_count = len(results["failed"])
        typer.echo(f"\n批量导入完成: 成功 {success_count}, 失败 {failed_count}")
        if results["failed"]:
            typer.echo("\n失败标的:")
            for item in results["failed"][:10]:
                typer.echo(f"  {item['symbol']}: {item['error']}")
            if len(results["failed"]) > 10:
                typer.echo(f"  ... 还有 {len(results['failed']) - 10} 个")
    except Exception as e:
        typer.echo(f"获取失败: {e}", err=True)
        raise typer.Exit(1)


@data_app.command("factor-list")
def list_factor_symbols_cmd():
    """列出已有后复权因子数据的标的"""
    from backend.db.factor import list_factor_symbols

    symbols = list_factor_symbols()
    if not symbols:
        typer.echo("暂无因子数据")
    else:
        typer.echo(f"\n共 {len(symbols)} 个标的有因子数据:\n")
        for sym in symbols:
            typer.echo(f"  {sym}")


@data_app.command("factor-show")
def show_factor_cmd(
    symbol: str = typer.Argument(..., help="标的代码"),
    start_date: str | None = typer.Option(None, help="开始日期 YYYY-MM-DD"),
    end_date: str | None = typer.Option(None, help="结束日期 YYYY-MM-DD"),
):
    """显示后复权因子数据"""
    from backend.db.factor import _query_factor

    start_dt = datetime.strptime(start_date, "%Y-%m-%d") if start_date else None
    end_dt = datetime.strptime(end_date, "%Y-%m-%d") if end_date else None

    data = _query_factor(symbol, start_dt, end_dt)

    if len(data) == 0:
        typer.echo(f"无 {symbol} 的因子数据")
        return

    typer.echo(f"\n{symbol} 后复权因子数据 (共 {len(data)} 条):\n")
    typer.echo(data.to_string(index=False))


# 回测子命令
backtest_app = typer.Typer(name="backtest", help="回测管理")
app.add_typer(backtest_app, name="backtest")


def _print_backtest_result(result: dict):
    """打印回测结果"""
    from prettytable import PrettyTable

    if result.get("status") == "failed":
        typer.echo(f"\n回测失败: {result.get('error', '未知错误')}")
        return

    typer.echo("\n回测完成!")
    typer.echo(f"总收益率: {result['metrics']['total_return']:.2%}")
    typer.echo(f"年化收益: {result['metrics']['annual_return']:.2%}")
    typer.echo(f"夏普比率: {result['metrics']['sharpe_ratio']:.2f}")
    typer.echo(f"最大回撤: {result['metrics']['max_drawdown']:.2%}")
    typer.echo(f"胜率: {result['metrics']['win_rate']:.2%}")
    typer.echo(f"交易次数: {len(result['trades'])}")

    trades = result["trades"]
    open_round_trips: dict[str, dict] = {}
    realized_pnl = 0.0
    for trade in trades:
        symbol = trade["symbol"]
        quantity = trade["quantity"]
        price = trade["price"]
        commission = trade.get("commission", 0.0) or 0.0

        if trade["side"] == "buy":
            open_round_trips[symbol] = {
                "quantity": quantity,
                "cost": price * quantity,
                "buy_commission": commission,
            }
        elif symbol in open_round_trips:
            position = open_round_trips.pop(symbol)
            gross_pnl = price * quantity - position["cost"]
            realized_pnl += gross_pnl - position["buy_commission"] - commission

    if realized_pnl or trades:
        typer.echo(f"已平仓净收益: {realized_pnl:.2f}")

    open_positions = result.get("open_positions", [])
    if open_positions:
        unrealized_pnl = sum(item["unrealized_pnl"] for item in open_positions)
        typer.echo(f"未平仓浮盈亏: {unrealized_pnl:.2f}")
        for item in open_positions:
            typer.echo(
                f"  未平仓 {item['symbol']}: qty={item['quantity']} avg_cost={item['avg_cost']:.4f} "
                f"last={item['last_price']:.4f} 浮盈亏={item['unrealized_pnl']:.2f}"
            )

    if trades:
        table = PrettyTable()
        table.field_names = ["时间", "方向", "标的", "价格", "数量", "手续费", "盈亏"]
        table.align["时间"] = "l"
        table.align["方向"] = "l"
        table.align["标的"] = "l"
        table.align["价格"] = "r"
        table.align["数量"] = "r"
        table.align["手续费"] = "r"
        table.align["盈亏"] = "r"
        table.float_format = ".4"

        for t in result["trades"]:
            table.add_row([
                str(t["timestamp"]),
                t["side"],
                t["symbol"],
                t["price"],
                t["quantity"],
                f"{t.get('commission', 0):.2f}" if t.get("commission") else "-",
                f"{t.get('pnl', 0):.2f}" if t.get("pnl") else "-",
            ])

        typer.echo(f"\n{table}")


@backtest_app.command("run")
def run_backtest_cmd(
    strategy_id: int = typer.Argument(..., help="策略 ID"),
    symbol: str = typer.Argument(..., help="标的代码、逗号列表或 @标的池"),
    start_date: str = typer.Argument(..., help="开始日期 YYYY-MM-DD"),
    end_date: str = typer.Argument(..., help="结束日期 YYYY-MM-DD"),
    initial_capital: float = typer.Option(1000000.0, help="初始资金"),
    commission: float = typer.Option(0.0003, help="手续费率"),
    slippage: float = typer.Option(0.001, help="滑点比例，如 0.001 表示 0.1%"),
    period: str = typer.Option("1min", help="K线周期: 1min/5min/15min/30min/60min/120min/1D/1W/1M/1Q"),
    adjust: str = typer.Option("hfq", help="复权方式: none/qfq/hfq"),
):
    """运行回测（使用数据库中的策略）"""
    from backend.db import SessionLocal, get_market_data
    from backend.engine import BacktestEngine
    from backend.models import Backtest, Strategy

    resolved_symbols, display_target = _resolve_target_symbols(symbol)

    # 查询数据
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    data_dict = get_market_data(resolved_symbols, start_dt, end_dt, period=period, adjust=adjust)

    missing = [item for item in resolved_symbols if item not in data_dict or data_dict[item].empty]
    if missing:
        typer.echo(f"无以下标的的K线数据: {', '.join(missing)}", err=True)
        raise typer.Exit(1)

    with SessionLocal() as db:
        strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
        if not strategy:
            typer.echo(f"策略 ID {strategy_id} 不存在", err=True)
            raise typer.Exit(1)

        typer.echo(f"开始回测: {display_target} ({start_date} ~ {end_date}) period={period} adjust={adjust}")
        if len(resolved_symbols) > 1:
            typer.echo(f"  解析标的: {', '.join(resolved_symbols)}")

        # 执行回测
        engine = BacktestEngine(
            strategy_code=strategy.code,
            data=data_dict[resolved_symbols[0]] if len(resolved_symbols) == 1 else data_dict,
            symbol=resolved_symbols if len(resolved_symbols) > 1 else resolved_symbols[0],
            initial_capital=initial_capital,
            commission=commission,
            slippage=slippage,
            period=period,
        )
        result = engine.run()

        try:
            backtest = Backtest(
                strategy_id=strategy_id,
                symbol=display_target,
                start_date=datetime.strptime(start_date, "%Y-%m-%d").date(),
                end_date=datetime.strptime(end_date, "%Y-%m-%d").date(),
                initial_capital=Decimal(str(initial_capital)),
                commission=Decimal(str(commission)),
                slippage=Decimal(str(slippage)),
                period=period,
                adjust=adjust,
                status=result["status"],
                total_return=Decimal(str(result["metrics"]["total_return"])),
                annual_return=Decimal(str(result["metrics"]["annual_return"])),
                sharpe_ratio=Decimal(str(result["metrics"]["sharpe_ratio"])),
                max_drawdown=Decimal(str(result["metrics"]["max_drawdown"])),
                win_rate=Decimal(str(result["metrics"]["win_rate"])),
                equity_curve=json.dumps(result["equity_curve"]),
            )
            db.add(backtest)
            db.flush()

            _persist_trades(db, backtest.id, result["trades"])
            db.commit()
        except Exception as e:
            db.rollback()
            typer.echo(f"保存回测结果失败: {e}", err=True)
            raise typer.Exit(1)

        _print_backtest_result(result)


@backtest_app.command("run-file")
def run_backtest_file_cmd(
    strategy_file: Path = typer.Argument(..., help="策略文件路径 (.py)", exists=True),
    symbol: str = typer.Argument(..., help="标的代码、逗号列表或 @标的池"),
    start_date: str = typer.Argument(..., help="开始日期 YYYY-MM-DD"),
    end_date: str = typer.Argument(..., help="结束日期 YYYY-MM-DD"),
    initial_capital: float = typer.Option(1000000.0, help="初始资金"),
    commission: float = typer.Option(0.0003, help="手续费率"),
    slippage: float = typer.Option(0.001, help="滑点比例，如 0.001 表示 0.1%"),
    period: str = typer.Option("1min", help="K线周期: 1min/5min/15min/30min/60min/120min/1D/1W/1M/1Q"),
    adjust: str = typer.Option("hfq", help="复权方式: none/qfq/hfq"),
    params: str = typer.Option("{}", help="策略参数 (JSON), 如 '{\"short_period\":10,\"long_period\":30}'"),
    save: bool = typer.Option(False, "--save", help="保存回测结果到数据库"),
    strategy_name: str = typer.Option("", "--strategy-name", help="保存时使用的策略名称，默认取文件名"),
    strategy_id: int = typer.Option(0, "--strategy-id", help="关联已有策略 ID，与 --strategy-name 互斥"),
    plot: bool = typer.Option(False, "--plot", help="生成交互式图表"),
    plot_backend: str = typer.Option("pyecharts", help="图表引擎: pyecharts, lightweight"),
    plot_output: str = typer.Option("backtest_chart.html", "--plot-output", help="输出 HTML 文件路径"),
    plot_show: bool = typer.Option(False, "--plot-show", help="在桌面窗口中打开图表"),
):
    """运行回测（直接使用策略文件，无需数据库）"""
    from backend.db import get_market_data
    from backend.engine import BacktestEngine

    # 读取策略文件
    if not strategy_file.suffix == ".py":
        typer.echo("策略文件必须是 .py 文件", err=True)
        raise typer.Exit(1)

    strategy_code = strategy_file.read_text(encoding="utf-8")

    # 验证策略代码
    try:
        from backend.engine.executor import StrategyExecutor
        executor = StrategyExecutor(strategy_code)
        executor.load()
    except ValueError as e:
        typer.echo(f"策略代码无效: {e}", err=True)
        raise typer.Exit(1)

    # 解析标的列表
    symbols, display_target = _resolve_target_symbols(symbol)

    # 查询行情数据
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    data_dict = get_market_data(symbols, start_dt, end_dt, period=period, adjust=adjust)

    missing = [s for s in symbols if s not in data_dict or data_dict[s].empty]
    if missing:
        typer.echo(f"无以下标的的K线数据: {', '.join(missing)}", err=True)
        raise typer.Exit(1)

    # 解析策略参数
    try:
        strategy_params = json.loads(params)
    except json.JSONDecodeError as e:
        typer.echo(f"策略参数 JSON 解析失败: {e}", err=True)
        raise typer.Exit(1)

    typer.echo(f"开始回测: {display_target} ({start_date} ~ {end_date})")
    if len(symbols) > 1:
        typer.echo(f"  解析标的: {', '.join(symbols)}")
    typer.echo(f"  策略文件: {strategy_file}")
    typer.echo(f"  K线周期: {period}  复权: {adjust}")
    if strategy_params:
        typer.echo(f"  策略参数: {strategy_params}")
    for sym in symbols:
        typer.echo(f"  {sym} 数据量: {len(data_dict[sym])} bars")

    # 执行回测
    engine = BacktestEngine(
        strategy_code=strategy_code,
        data=data_dict,
        symbol=symbols,
        initial_capital=initial_capital,
        commission=commission,
        slippage=slippage,
        period=period,
        params=strategy_params,
    )
    result = engine.run()

    _print_backtest_result(result)

    if plot:
        from backend.plotting import ChartBuilder, LayerSpec, PlotConfig

        plot_symbol = symbols[0]
        kline_data = data_dict[plot_symbol]
        config = PlotConfig(
            title=f"{plot_symbol} Backtest",
            layers=[
                LayerSpec(indicator="ma", name="MA(5)", params={"period": 5}, color="#F44336"),
                LayerSpec(indicator="ma", name="MA(20)", params={"period": 20}, color="#2196F3"),
                LayerSpec(indicator="volume", name="Volume", pane="volume"),
            ],
            show_trades=True,
            show_equity_curve=True,
            show_drawdown=True,
        )
        builder = ChartBuilder(result, kline_data, config=config)
        render_result = builder.render(renderer_name=plot_backend, output=plot_output, show=plot_show)
        if render_result.filepath:
            typer.echo(f"图表已保存: {render_result.filepath}")

    if save:
        if result["status"] == "failed":
            typer.echo("回测失败，不保存结果", err=True)
            raise typer.Exit(1)

        if strategy_id and strategy_name:
            typer.echo("--strategy-id 和 --strategy-name 不能同时使用", err=True)
            raise typer.Exit(1)

        from backend.db import SessionLocal, init_db
        from backend.models import Backtest, Strategy

        init_db()

        with SessionLocal() as db:
            if strategy_id:
                strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
                if not strategy:
                    typer.echo(f"策略 ID {strategy_id} 不存在", err=True)
                    raise typer.Exit(1)
            else:
                strategy_name = (strategy_name or strategy_file.stem)[:100]
                strategy = db.query(Strategy).filter(
                    Strategy.name == strategy_name,
                    Strategy.code == strategy_code,
                ).first()
                if not strategy:
                    strategy = Strategy(name=strategy_name, code=strategy_code)
                    db.add(strategy)

            try:
                backtest = Backtest(
                    strategy_id=strategy.id,
                    symbol=display_target,
                    start_date=datetime.strptime(start_date, "%Y-%m-%d").date(),
                    end_date=datetime.strptime(end_date, "%Y-%m-%d").date(),
                    initial_capital=Decimal(str(initial_capital)),
                    commission=Decimal(str(commission)),
                    slippage=Decimal(str(slippage)),
                    period=period,
                    adjust=adjust,
                    status=result["status"],
                    total_return=Decimal(str(result["metrics"]["total_return"])),
                    annual_return=Decimal(str(result["metrics"]["annual_return"])),
                    sharpe_ratio=Decimal(str(result["metrics"]["sharpe_ratio"])),
                    max_drawdown=Decimal(str(result["metrics"]["max_drawdown"])),
                    win_rate=Decimal(str(result["metrics"]["win_rate"])),
                    equity_curve=json.dumps(result["equity_curve"]),
                )
                db.add(backtest)
                db.flush()

                _persist_trades(db, backtest.id, result["trades"])
                db.commit()
                saved_backtest_id = backtest.id
            except Exception as e:
                db.rollback()
                typer.echo(f"保存回测结果失败: {e}", err=True)
                raise typer.Exit(1)

        typer.echo(f"回测结果已保存，ID: {saved_backtest_id}")


@backtest_app.command("list")
def list_backtests_cmd(limit: int = typer.Option(20, help="显示条数")):
    """列出最近的回测记录"""
    from backend.db import SessionLocal
    from backend.models import Backtest

    with SessionLocal() as db:
        backtests = db.query(Backtest).order_by(Backtest.id.desc()).limit(limit).all()

        if not backtests:
            typer.echo("暂无回测记录")
            return

        typer.echo("\n最近回测记录:\n")
        for bt in backtests:
            typer.echo(
                f"ID {bt.id}: {bt.symbol} | {bt.start_date} ~ {bt.end_date} | "
                f"收益率: {float(bt.total_return or 0):.2%} | 状态: {bt.status}"
            )


# 策略子命令
strategy_app = typer.Typer(name="strategy", help="策略管理")
app.add_typer(strategy_app, name="strategy")


@strategy_app.command("list")
def list_strategies_cmd():
    """列出所有策略"""
    from backend.db import SessionLocal
    from backend.models import Strategy

    with SessionLocal() as db:
        strategies = db.query(Strategy).order_by(Strategy.id.desc()).all()

        if not strategies:
            typer.echo("暂无策略")
            return

        typer.echo("\n策略列表:\n")
        for s in strategies:
            typer.echo(f"ID {s.id}: {s.name} - {s.description}")


@strategy_app.command("show")
def show_strategy_cmd(strategy_id: int):
    """显示策略详情"""
    from backend.db import SessionLocal
    from backend.models import Strategy

    with SessionLocal() as db:
        strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
        if not strategy:
            typer.echo(f"策略 ID {strategy_id} 不存在", err=True)
            raise typer.Exit(1)

        typer.echo(f"\n策略: {strategy.name}")
        typer.echo(f"描述: {strategy.description}")
        typer.echo(f"创建时间: {strategy.created_at}")
        typer.echo(f"\n代码:\n{strategy.code}")


@strategy_app.command("create")
def create_strategy_cmd(
    name: str = typer.Option(..., "--name", "-n", help="策略名称"),
    description: str = typer.Option("", "--description", "-d", help="策略描述"),
    file_path: Path = typer.Option(..., "--file", "-f", help="策略代码文件路径", exists=True),
):
    """创建新策略"""
    from backend.db import SessionLocal
    from backend.models import Strategy

    code = file_path.read_text()

    with SessionLocal() as db:
        strategy = Strategy(name=name, description=description, code=code)
        db.add(strategy)
        db.commit()
        db.refresh(strategy)
        typer.echo(f"策略创建成功，ID: {strategy.id}")


if __name__ == "__main__":
    app()

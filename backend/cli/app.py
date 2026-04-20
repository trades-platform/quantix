"""Quantix CLI"""

import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import typer

app = typer.Typer(name="quantix", help="量化回测平台")


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


# 数据管理子命令
data_app = typer.Typer(name="data", help="数据管理")
app.add_typer(data_app, name="data")


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

    start_dt = datetime.strptime(start_date, "%Y-%m-%d") if start_date else None
    end_dt = datetime.strptime(end_date, "%Y-%m-%d") if end_date else None

    data = _query_kline(symbol, start_dt, end_dt)

    if len(data) == 0:
        typer.echo(f"无 {symbol} 的数据")
        return

    typer.echo(f"\n{symbol} K线数据 (共 {len(data)} 条):\n")
    typer.echo(data.head(limit).to_string(index=False))


@data_app.command("fetch")
def fetch_kline_cmd(
    symbol: str = typer.Argument(..., help="标的代码，如 600000.SH"),
    period: str = typer.Option("min1", help="K线周期: min1/min5/min15/min30/min60/day/week/month"),
    start_date: str | None = typer.Option(None, help="开始日期 YYYY-MM-DD"),
    end_date: str | None = typer.Option(None, help="结束日期 YYYY-MM-DD"),
    increment: bool = typer.Option(False, help="增量导入（从最新数据时间到当前）"),
):
    """从 AmazingData 获取并导入K线数据"""
    from backend.data import fetch_kline as data_fetch_kline

    period_int = _parse_period(period)

    try:
        count = data_fetch_kline(
            symbol,
            period_int,
            start_date,
            end_date,
            increment,
        )
        if increment:
            typer.echo(f"增量导入完成: {symbol} 新增 {count} 条数据")
        else:
            typer.echo(f"导入完成: {symbol} 共 {count} 条数据")
    except Exception as e:
        typer.echo(f"获取失败: {e}", err=True)
        raise typer.Exit(1)


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
    from backend.data import fetch_kline as data_fetch_kline

    period_int = _parse_period(period)

    success = []
    failed = []

    for i, symbol in enumerate(symbols, 1):
        typer.echo(f"[{i}/{len(symbols)}] 导入 {symbol}...")
        try:
            count = data_fetch_kline(
                symbol,
                period_int,
                start_date,
                end_date,
                increment,
            )
            success.append({"symbol": symbol, "count": count})
        except Exception as e:
            failed.append({"symbol": symbol, "error": str(e)})
            typer.echo(f"  失败: {e}", err=True)

    typer.echo(f"\n批量导入完成:")
    typer.echo(f"  成功: {len(success)}")
    typer.echo(f"  失败: {len(failed)}")

    if failed:
        typer.echo("\n失败标的:")
        for item in failed:
            typer.echo(f"  {item['symbol']}: {item['error']}")

    if failed:
        raise typer.Exit(1)


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

    if result["trades"]:
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
    symbol: str = typer.Argument(..., help="标的代码"),
    start_date: str = typer.Argument(..., help="开始日期 YYYY-MM-DD"),
    end_date: str = typer.Argument(..., help="结束日期 YYYY-MM-DD"),
    initial_capital: float = typer.Option(1000000.0, help="初始资金"),
    commission: float = typer.Option(0.0003, help="手续费率"),
    slippage: float = typer.Option(0.001, help="滑点比例，如 0.001 表示 0.1%"),
    period: str = typer.Option("1min", help="K线周期: 1min/5min/15min/30min/60min/120min/1D/1W/1M/1Q"),
    adjust: str = typer.Option("hfq", help="复权方式: none/qfq/hfq"),
):
    """运行回测（使用数据库中的策略）"""
    from decimal import Decimal

    from backend.db import SessionLocal, get_market_data
    from backend.engine import BacktestEngine
    from backend.models import Backtest, Strategy

    with SessionLocal() as db:
        strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
        if not strategy:
            typer.echo(f"策略 ID {strategy_id} 不存在", err=True)
            raise typer.Exit(1)

        # 创建回测记录
        backtest = Backtest(
            strategy_id=strategy_id,
            symbol=symbol,
            start_date=datetime.strptime(start_date, "%Y-%m-%d").date(),
            end_date=datetime.strptime(end_date, "%Y-%m-%d").date(),
            initial_capital=Decimal(str(initial_capital)),
            commission=Decimal(str(commission)),
            status="running",
        )
        db.add(backtest)
        db.commit()
        db.refresh(backtest)

        # 查询数据
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        data_dict = get_market_data(symbol, start_dt, end_dt, period=period, adjust=adjust)

        if not data_dict or symbol not in data_dict:
            typer.echo(f"无 {symbol} 的K线数据", err=True)
            raise typer.Exit(1)

        typer.echo(f"开始回测: {symbol} ({start_date} ~ {end_date}) period={period} adjust={adjust}")

        # 执行回测
        engine = BacktestEngine(
            strategy_code=strategy.code,
            data=data_dict[symbol],
            symbol=symbol,
            initial_capital=initial_capital,
            commission=commission,
            slippage=slippage,
            period=period,
        )
        result = engine.run()

        # 更新结果
        backtest.status = result["status"]
        backtest.total_return = Decimal(str(result["metrics"]["total_return"]))
        backtest.annual_return = Decimal(str(result["metrics"]["annual_return"]))
        backtest.sharpe_ratio = Decimal(str(result["metrics"]["sharpe_ratio"]))
        backtest.max_drawdown = Decimal(str(result["metrics"]["max_drawdown"]))
        backtest.win_rate = Decimal(str(result["metrics"]["win_rate"]))
        backtest.equity_curve = json.dumps(result["equity_curve"])
        db.commit()

        _print_backtest_result(result)


@backtest_app.command("run-file")
def run_backtest_file_cmd(
    strategy_file: Path = typer.Argument(..., help="策略文件路径 (.py)", exists=True),
    symbol: str = typer.Argument(..., help="标的代码"),
    start_date: str = typer.Argument(..., help="开始日期 YYYY-MM-DD"),
    end_date: str = typer.Argument(..., help="结束日期 YYYY-MM-DD"),
    initial_capital: float = typer.Option(1000000.0, help="初始资金"),
    commission: float = typer.Option(0.0003, help="手续费率"),
    slippage: float = typer.Option(0.001, help="滑点比例，如 0.001 表示 0.1%"),
    period: str = typer.Option("1min", help="K线周期: 1min/5min/15min/30min/60min/120min/1D/1W/1M/1Q"),
    adjust: str = typer.Option("hfq", help="复权方式: none/qfq/hfq"),
    params: str = typer.Option("{}", help="策略参数 (JSON), 如 '{\"short_period\":10,\"long_period\":30}'"),
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

    # 查询行情数据
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    data_dict = get_market_data(symbol, start_dt, end_dt, period=period, adjust=adjust)

    if not data_dict or symbol not in data_dict:
        typer.echo(f"无 {symbol} 的K线数据", err=True)
        raise typer.Exit(1)

    # 解析策略参数
    try:
        strategy_params = json.loads(params)
    except json.JSONDecodeError as e:
        typer.echo(f"策略参数 JSON 解析失败: {e}", err=True)
        raise typer.Exit(1)

    kline_data = data_dict[symbol]
    typer.echo(f"开始回测: {symbol} ({start_date} ~ {end_date})")
    typer.echo(f"  策略文件: {strategy_file}")
    typer.echo(f"  K线周期: {period}  复权: {adjust}")
    if strategy_params:
        typer.echo(f"  策略参数: {strategy_params}")
    typer.echo(f"  数据量: {len(kline_data)} bars")

    # 执行回测
    engine = BacktestEngine(
        strategy_code=strategy_code,
        data=kline_data,
        symbol=symbol,
        initial_capital=initial_capital,
        commission=commission,
        slippage=slippage,
        period=period,
        params=strategy_params,
    )
    result = engine.run()

    _print_backtest_result(result)


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

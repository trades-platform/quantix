"""Quantix CLI"""

import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import typer

app = typer.Typer(name="quantix", help="量化回测平台")

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
    from backend.db import list_symbols

    symbols = list_symbols()
    if not symbols:
        typer.echo("暂无数据")
    else:
        typer.echo("\n".join(symbols))


@data_app.command("show")
def show_kline_cmd(
    symbol: str = typer.Argument(..., help="标的代码"),
    start_date: str | None = typer.Option(None, help="开始日期 YYYY-MM-DD"),
    end_date: str | None = typer.Option(None, help="结束日期 YYYY-MM-DD"),
    limit: int = typer.Option(10, help="显示行数"),
):
    """显示K线数据"""
    from backend.db import query_kline

    start_dt = datetime.strptime(start_date, "%Y-%m-%d") if start_date else None
    end_dt = datetime.strptime(end_date, "%Y-%m-%d") if end_date else None

    data = query_kline(symbol, start_dt, end_dt)

    if len(data) == 0:
        typer.echo(f"无 {symbol} 的数据")
        return

    typer.echo(f"\n{symbol} K线数据 (共 {len(data)} 条):\n")
    typer.echo(data.head(limit).to_string(index=False))


# 回测子命令
backtest_app = typer.Typer(name="backtest", help="回测管理")
app.add_typer(backtest_app, name="backtest")


@backtest_app.command("run")
def run_backtest_cmd(
    strategy_id: int = typer.Argument(..., help="策略 ID"),
    symbol: str = typer.Argument(..., help="标的代码"),
    start_date: str = typer.Argument(..., help="开始日期 YYYY-MM-DD"),
    end_date: str = typer.Argument(..., help="结束日期 YYYY-MM-DD"),
    initial_capital: float = typer.Option(1000000.0, help="初始资金"),
    commission: float = typer.Option(0.0003, help="手续费率"),
):
    """运行回测"""
    from decimal import Decimal

    from backend.db import SessionLocal, query_kline
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
        kline_data = query_kline(symbol, start_dt, end_dt)

        if len(kline_data) == 0:
            typer.echo(f"无 {symbol} 的K线数据", err=True)
            raise typer.Exit(1)

        typer.echo(f"开始回测: {symbol} ({start_date} ~ {end_date})")

        # 执行回测
        engine = BacktestEngine(
            strategy_code=strategy.code,
            data=kline_data,
            symbol=symbol,
            initial_capital=initial_capital,
            commission=commission,
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

        # 输出结果
        typer.echo("\n回测完成!")
        typer.echo(f"总收益率: {result['metrics']['total_return']:.2%}")
        typer.echo(f"年化收益: {result['metrics']['annual_return']:.2%}")
        typer.echo(f"夏普比率: {result['metrics']['sharpe_ratio']:.2f}")
        typer.echo(f"最大回撤: {result['metrics']['max_drawdown']:.2%}")
        typer.echo(f"胜率: {result['metrics']['win_rate']:.2%}")
        typer.echo(f"交易次数: {len(result['trades'])}")


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

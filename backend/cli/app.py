"""Quantix CLI"""

import typer

app = typer.Typer(name="quantix", help="量化回测平台")


@app.command()
def serve(host: str = "0.0.0.0", port: int = 8000):
    """启动 API 服务"""
    import uvicorn

    uvicorn.run("backend.main:app", host=host, port=port, reload=True)


@app.command()
def initdb():
    """初始化数据库"""
    from backend.db.sqlite import init_db

    init_db()
    typer.echo("数据库初始化完成")


if __name__ == "__main__":
    app()

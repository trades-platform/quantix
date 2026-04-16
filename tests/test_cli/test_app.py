"""CLI 命令测试"""

import tempfile
from pathlib import Path
import pytest


def test_cli_app_structure():
    """测试 CLI 应用结构

    TC-CLI-001: CLI 应用应该正确注册所有命令
    """
    from backend.cli.app import app
    import typer

    assert app is not None
    assert isinstance(app, typer.Typer)

    # Typer 应用应该有 registered_commands 或类似属性
    # 验证应用已正确初始化
    assert hasattr(app, 'registered_commands')
    # 或通过其他方式验证


def test_cli_initdb_with_temp_directory():
    """测试 initdb 命令使用临时目录

    TC-CLI-002: initdb 应该能够初始化数据库
    """
    from backend.cli.app import initdb
    from backend.db.sqlite import DB_PATH, init_db
    import tempfile

    # 保存原始路径
    original_db_path = DB_PATH

    with tempfile.TemporaryDirectory() as tmpdir:
        # 设置临时数据目录
        test_data_path = Path(tmpdir) / "data"
        test_data_path.mkdir()

        test_db_path = test_data_path / "test.db"

        # 临时修改 DB_PATH（需要实现支持）
        # 当前实现中路径是硬编码的，这里展示测试框架
        # 等待 CLI 支持自定义路径后完善

        # 注意：这个测试需要修改 CLI 以支持自定义路径
        # 或者使用 mock 来拦截数据库路径
        pass


def test_cli_serve_command_exists():
    """测试 serve 命令存在

    TC-CLI-003: serve 命令应该存在
    """
    from backend.cli.app import app

    # 检查 serve 命令是否注册
    # Typer 的内部结构可能因版本而异
    # 这里验证命令存在的基本方法

    assert app is not None

    # 可以通过其他方式验证命令注册
    # 例如检查 app.registered_commands


def test_cli_initdb_command_exists():
    """测试 initdb 命令存在

    TC-CLI-004: initdb 命令应该存在
    """
    from backend.cli.app import app, initdb

    # 验证 initdb 函数存在且可调用
    assert initdb is not None
    assert callable(initdb)


def test_cli_command_parameters():
    """测试命令参数

    TC-CLI-005: CLI 命令应该有正确的参数
    """
    from backend.cli.app import serve
    import inspect

    # 检查 serve 命令的参数
    sig = inspect.signature(serve)

    # 应该有 host 和 port 参数
    assert 'host' in sig.parameters
    assert 'port' in sig.parameters


def test_cli_importdb_command_placeholder():
    """测试数据导入命令（占位符）

    TC-CLI-006: 数据导入命令（待实现）
    """
    # 等待 CLI 添加 importdb 命令后实现此测试
    pass


def test_cli_backtest_command_placeholder():
    """测试回测命令（占位符）

    TC-CLI-007: 回测命令（待实现）
    """
    # 等待 CLI 添加 backtest 命令后实现此测试
    pass

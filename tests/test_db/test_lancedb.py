"""LanceDB K线数据库连接测试"""

import tempfile
from pathlib import Path

import pytest
import lancedb


def test_lancedb_connection():
    """测试 LanceDB 连接创建

    TC-DB-006: 应该能够创建 LanceDB 连接
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db_path = Path(tmpdir) / "kline"

        # 创建连接
        db = lancedb.connect(str(test_db_path))

        assert db is not None
        assert isinstance(db, lancedb.db.DBConnection)


def test_lancedb_directory_creation():
    """测试 LanceDB 目录创建

    TC-DB-007: 连接时应该自动创建目录
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db_path = Path(tmpdir) / "kline" / "nested"

        # 目录不存在
        assert not test_db_path.exists()

        # 创建连接应该自动创建目录
        db = lancedb.connect(str(test_db_path))

        assert test_db_path.exists()
        assert test_db_path.is_dir()


def test_lancedb_table_operations():
    """测试 LanceDB 表操作

    TC-DB-008: 应该能够创建和操作表
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db_path = Path(tmpdir) / "kline"

        db = lancedb.connect(str(test_db_path))

        # 创建表
        import pandas as pd
        from datetime import datetime

        data = pd.DataFrame({
            'timestamp': [datetime(2024, 1, i) for i in range(1, 6)],
            'open': [10.0 + i * 0.1 for i in range(5)],
            'high': [10.5 + i * 0.1 for i in range(5)],
            'low': [9.5 + i * 0.1 for i in range(5)],
            'close': [10.2 + i * 0.1 for i in range(5)],
            'volume': [1000000] * 5,
        })

        # 创建表
        db.create_table("test_kline", data)

        # 验证表存在
        tables = db.list_tables()
        assert "test_kline" in str(tables)

        # 查询数据
        table = db.open_table("test_kline")
        result = table.to_pandas()

        assert len(result) == 5
        assert list(result.columns) == ['timestamp', 'open', 'high', 'low', 'close', 'volume']


def test_lancedb_kline_schema():
    """测试 K线数据 Schema

    TC-DB-009: K线表应该包含正确的字段
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db_path = Path(tmpdir) / "kline"

        db = lancedb.connect(str(test_db_path))

        import pandas as pd
        from datetime import datetime
        import pyarrow as pa

        # 定义 Schema
        schema = pa.schema([
            ('timestamp', pa.timestamp('s')),
            ('open', pa.float64()),
            ('high', pa.float64()),
            ('low', pa.float64()),
            ('close', pa.float64()),
            ('volume', pa.int64()),
            ('amount', pa.float64()),
        ])

        # 创建表
        data = pd.DataFrame({
            'timestamp': [datetime(2024, 1, 1)],
            'open': [10.0],
            'high': [10.5],
            'low': [9.5],
            'close': [10.2],
            'volume': [1000000],
            'amount': [10000000.0],
        })

        db.create_table("kline_600000", data, schema=schema)

        # 验证 Schema
        table = db.open_table("kline_600000")
        table_schema = table.schema

        field_names = [field.name for field in table_schema]
        required_fields = ['timestamp', 'open', 'high', 'low', 'close', 'volume']

        for field in required_fields:
            assert field in field_names


def test_lancedb_persistence():
    """测试数据持久化

    TC-DB-010: 数据应该持久化到磁盘
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db_path = Path(tmpdir) / "kline"

        import pandas as pd
        from datetime import datetime

        # 第一次连接并创建表
        db1 = lancedb.connect(str(test_db_path))

        data1 = pd.DataFrame({
            'timestamp': [datetime(2024, 1, 1)],
            'open': [10.0],
            'high': [10.5],
            'low': [9.5],
            'close': [10.2],
            'volume': [1000000],
        })

        db1.create_table("persistent_kline", data1)

        # 关闭连接
        del db1

        # 第二次连接并读取数据
        db2 = lancedb.connect(str(test_db_path))
        table = db2.open_table("persistent_kline")
        data2 = table.to_pandas()

        assert len(data2) == 1
        assert data2['close'].iloc[0] == 10.2


def test_lancedb_symbol_naming():
    """测试标的表命名

    TC-DB-011: 不同标的应该对应不同的表
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db_path = Path(tmpdir) / "kline"

        db = lancedb.connect(str(test_db_path))

        import pandas as pd
        from datetime import datetime

        symbols = ["600000.SH", "000001.SZ", "300001.SZ"]

        for symbol in symbols:
            data = pd.DataFrame({
                'timestamp': [datetime(2024, 1, 1)],
                'open': [10.0],
                'high': [10.5],
                'low': [9.5],
                'close': [10.2],
                'volume': [1000000],
            })

            table_name = f"kline_{symbol}"
            db.create_table(table_name, data)

        # 验证所有表都已创建
        tables = db.list_tables()

        for symbol in symbols:
            assert f"kline_{symbol}" in str(tables)

        assert len(str(tables).split(',')) == len(symbols)  # Approximate check

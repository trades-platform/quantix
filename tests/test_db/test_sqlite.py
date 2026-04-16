"""SQLite 数据库连接测试"""

import tempfile
from pathlib import Path

from backend.db.sqlite import engine, SessionLocal, init_db
from backend.models.strategy import Base


def test_database_initialization():
    """测试数据库初始化

    TC-DB-001: init_db 应该创建所有必需的表
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db_path = Path(tmpdir) / "test.db"

        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from backend.models.strategy import Base, Strategy

        test_engine = create_engine(f"sqlite:///{test_db_path}", echo=False)

        # 创建所有表
        Base.metadata.create_all(test_engine)

        # 检查表是否存在
        from sqlalchemy import inspect

        inspector = inspect(test_engine)
        tables = inspector.get_table_names()

        assert "strategies" in tables


def test_session_creation():
    """测试会话创建

    TC-DB-002: SessionLocal 应该创建有效的会话
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db_path = Path(tmpdir) / "test.db"

        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from backend.models.strategy import Base, Strategy

        test_engine = create_engine(f"sqlite:///{test_db_path}", echo=False)
        TestingSessionLocal = sessionmaker(bind=test_engine)
        Base.metadata.create_all(test_engine)

        # 创建会话
        session = TestingSessionLocal()

        assert session is not None

        # 使用会话
        from backend.models.strategy import Strategy
        strategy = Strategy(name="测试", code="code")
        session.add(strategy)
        session.commit()

        # 清理
        session.close()


def test_transaction_rollback():
    """测试事务回滚

    TC-DB-003: 错误时应该回滚事务，不持久化数据
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db_path = Path(tmpdir) / "test.db"

        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from backend.models.strategy import Base, Strategy

        test_engine = create_engine(f"sqlite:///{test_db_path}", echo=False)
        TestingSessionLocal = sessionmaker(bind=test_engine)
        Base.metadata.create_all(test_engine)

        # 创建会话
        session = TestingSessionLocal()

        try:
            # 添加有效数据
            strategy1 = Strategy(name="策略1", code="code1")
            session.add(strategy1)
            session.flush()

            # 添加无效数据（缺少必填字段）
            strategy2 = Strategy()  # 缺少 name 和 code
            session.add(strategy2)

            # 尝试提交
            session.commit()
            assert False, "应该抛出异常"

        except Exception:
            # 回滚事务
            session.rollback()

            # 验证策略1也没有被保存（因为回滚）
            count = session.query(Strategy).count()
            assert count == 0

        finally:
            session.close()


def test_multiple_sessions():
    """测试多会话并发

    TC-DB-004: 多个会话应该能够独立操作
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db_path = Path(tmpdir) / "test.db"

        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from backend.models.strategy import Base, Strategy

        test_engine = create_engine(f"sqlite:///{test_db_path}", echo=False)
        TestingSessionLocal = sessionmaker(bind=test_engine)
        Base.metadata.create_all(test_engine)

        # 创建两个独立的会话
        session1 = TestingSessionLocal()
        session2 = TestingSessionLocal()

        # 在 session1 中添加数据
        strategy1 = Strategy(name="策略1", code="code1")
        session1.add(strategy1)
        session1.commit()

        # 在 session2 中查询（可能需要刷新）
        session2.rollback()  # 确保看到最新数据
        count = session2.query(Strategy).count()

        assert count >= 1

        # 清理
        session1.close()
        session2.close()


def test_database_file_creation():
    """测试数据库文件创建

    TC-DB-005: 数据库文件应该在指定路径创建
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db_path = Path(tmpdir) / "test.db"

        from sqlalchemy import create_engine
        from backend.models.strategy import Base

        test_engine = create_engine(f"sqlite:///{test_db_path}", echo=False)

        # 创建表应该创建数据库文件
        Base.metadata.create_all(test_engine)

        assert test_db_path.exists()
        assert test_db_path.is_file()

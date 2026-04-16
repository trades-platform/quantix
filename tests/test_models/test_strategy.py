"""策略模型测试"""

import pytest
from datetime import datetime
from backend.models.strategy import Strategy


class TestStrategyModel:
    """策略模型测试类"""

    def test_strategy_creation(self, db_session):
        """测试创建策略

        TC-MODEL-001: 应该能够创建策略实例
        """
        strategy = Strategy(
            name="测试策略",
            description="这是一个测试策略",
            code="def handle_bar(context): return []"
        )

        db_session.add(strategy)
        db_session.commit()

        assert strategy.id is not None
        assert strategy.name == "测试策略"
        assert strategy.description == "这是一个测试策略"
        assert strategy.code == "def handle_bar(context): return []"

    def test_strategy_required_fields(self, db_session):
        """测试策略必填字段

        TC-MODEL-002: name 和 code 是必填字段
        """
        # 缺少 code 应该失败
        with pytest.raises(Exception):
            strategy = Strategy(name="测试")
            db_session.add(strategy)
            db_session.commit()

    def test_strategy_default_values(self, db_session):
        """测试策略默认值

        TC-MODEL-003: description 应该有默认值
        """
        strategy = Strategy(
            name="测试策略",
            code="def handle_bar(context): return []"
        )

        db_session.add(strategy)
        db_session.commit()

        assert strategy.description == ""

    def test_strategy_timestamps(self, db_session):
        """测试策略时间戳

        TC-MODEL-004: created_at 和 updated_at 应该自动设置
        """
        strategy = Strategy(
            name="测试策略",
            code="def handle_bar(context): return []"
        )

        db_session.add(strategy)
        db_session.commit()

        assert strategy.created_at is not None
        assert isinstance(strategy.created_at, datetime)
        assert strategy.updated_at is not None
        assert isinstance(strategy.updated_at, datetime)

    def test_strategy_update_timestamp(self, db_session):
        """测试策略更新时间戳

        TC-MODEL-005: updated_at 应该在更新时自动更新
        """
        strategy = Strategy(
            name="测试策略",
            code="def handle_bar(context): return []"
        )

        db_session.add(strategy)
        db_session.commit()

        original_updated_at = strategy.updated_at

        # 等待一小段时间确保时间戳不同
        import time
        time.sleep(0.01)

        strategy.name = "更新后的策略"
        db_session.commit()

        assert strategy.updated_at > original_updated_at

    def test_strategy_query(self, db_session):
        """测试查询策略

        TC-MODEL-006: 应该能够查询策略
        """
        strategy1 = Strategy(
            name="策略1",
            code="code1"
        )
        strategy2 = Strategy(
            name="策略2",
            code="code2"
        )

        db_session.add(strategy1)
        db_session.add(strategy2)
        db_session.commit()

        strategies = db_session.query(Strategy).all()

        assert len(strategies) == 2

    def test_strategy_filter_by_name(self, db_session):
        """测试按名称过滤策略

        TC-MODEL-007: 应该能够按名称查询策略
        """
        strategy = Strategy(
            name="特定名称策略",
            code="code"
        )

        db_session.add(strategy)
        db_session.commit()

        result = db_session.query(Strategy).filter(
            Strategy.name == "特定名称策略"
        ).first()

        assert result is not None
        assert result.name == "特定名称策略"

    def test_strategy_delete(self, db_session):
        """测试删除策略

        TC-MODEL-008: 应该能够删除策略
        """
        strategy = Strategy(
            name="待删除策略",
            code="code"
        )

        db_session.add(strategy)
        db_session.commit()
        strategy_id = strategy.id

        db_session.delete(strategy)
        db_session.commit()

        deleted = db_session.query(Strategy).filter(
            Strategy.id == strategy_id
        ).first()

        assert deleted is None

    def test_strategy_long_code(self, db_session):
        """测试长代码

        TC-MODEL-009: 应该支持长策略代码
        """
        long_code = "def handle_bar(context):\n"
        long_code += "\n".join([f"    pass # line {i}" for i in range(100)])

        strategy = Strategy(
            name="长代码策略",
            code=long_code
        )

        db_session.add(strategy)
        db_session.commit()

        assert len(strategy.code) == len(long_code)

    def test_strategy_unicode(self, db_session):
        """测试 Unicode 字符

        TC-MODEL-010: 应该支持 Unicode 字符
        """
        strategy = Strategy(
            name="量化策略🚀",
            description="这是一个包含中文和emoji的描述📈",
            code="def handle_bar(context): return []"
        )

        db_session.add(strategy)
        db_session.commit()

        assert strategy.name == "量化策略🚀"
        assert "emoji" in strategy.description

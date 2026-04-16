"""回测模型测试"""

import pytest
from datetime import datetime, date
from decimal import Decimal
from backend.models.backtest import Backtest, Trade
from backend.models.strategy import Strategy


class TestBacktestModel:
    """回测模型测试类"""

    def test_backtest_creation(self, db_session):
        """测试创建回测

        TC-MODEL-101: 应该能够创建回测实例
        """
        # 先创建策略
        strategy = Strategy(
            name="测试策略",
            code="def handle_bar(context): return []"
        )
        db_session.add(strategy)
        db_session.commit()

        # 创建回测
        backtest = Backtest(
            strategy_id=strategy.id,
            symbol="600000.SH",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            initial_capital=Decimal("1000000"),
            commission=Decimal("0.0003"),
            status="pending"
        )

        db_session.add(backtest)
        db_session.commit()

        assert backtest.id is not None
        assert backtest.symbol == "600000.SH"
        assert backtest.status == "pending"

    def test_backtest_required_fields(self, db_session):
        """测试回测必填字段

        TC-MODEL-102: strategy_id, symbol 等是必填字段
        """
        # 先创建策略
        strategy = Strategy(
            name="测试策略",
            code="code"
        )
        db_session.add(strategy)
        db_session.commit()

        # 缺少必填字段应该失败
        with pytest.raises(Exception):
            backtest = Backtest(strategy_id=strategy.id)
            db_session.add(backtest)
            db_session.commit()

    def test_backtest_default_status(self, db_session):
        """测试回测默认状态

        TC-MODEL-103: status 应该有默认值 "pending"
        """
        strategy = Strategy(
            name="测试策略",
            code="code"
        )
        db_session.add(strategy)
        db_session.commit()

        backtest = Backtest(
            strategy_id=strategy.id,
            symbol="600000.SH",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            initial_capital=Decimal("1000000"),
            commission=Decimal("0.0003")
        )

        db_session.add(backtest)
        db_session.commit()

        assert backtest.status == "pending"

    def test_backtest_metrics(self, db_session):
        """测试回测指标

        TC-MODEL-104: 应该能够存储性能指标
        """
        strategy = Strategy(
            name="测试策略",
            code="code"
        )
        db_session.add(strategy)
        db_session.commit()

        backtest = Backtest(
            strategy_id=strategy.id,
            symbol="600000.SH",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            initial_capital=Decimal("1000000"),
            commission=Decimal("0.0003"),
            status="completed",
            total_return=Decimal("0.15"),
            annual_return=Decimal("0.12"),
            sharpe_ratio=Decimal("1.5"),
            max_drawdown=Decimal("-0.08"),
            win_rate=Decimal("0.6")
        )

        db_session.add(backtest)
        db_session.commit()

        assert float(backtest.total_return) == 0.15
        assert float(backtest.sharpe_ratio) == 1.5

    def test_backtest_strategy_relationship(self, db_session):
        """测试回测与策略的关系

        TC-MODEL-105: 回测应该关联到策略
        """
        strategy = Strategy(
            name="测试策略",
            code="code"
        )
        db_session.add(strategy)
        db_session.commit()

        backtest = Backtest(
            strategy_id=strategy.id,
            symbol="600000.SH",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            initial_capital=Decimal("1000000"),
            commission=Decimal("0.0003")
        )

        db_session.add(backtest)
        db_session.commit()

        assert backtest.strategy_id == strategy.id

    def test_backtest_created_at(self, db_session):
        """测试回测创建时间

        TC-MODEL-106: created_at 应该自动设置
        """
        strategy = Strategy(
            name="测试策略",
            code="code"
        )
        db_session.add(strategy)
        db_session.commit()

        backtest = Backtest(
            strategy_id=strategy.id,
            symbol="600000.SH",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            initial_capital=Decimal("1000000"),
            commission=Decimal("0.0003")
        )

        db_session.add(backtest)
        db_session.commit()

        assert backtest.created_at is not None
        assert isinstance(backtest.created_at, datetime)


class TestTradeModel:
    """交易模型测试类"""

    def test_trade_creation(self, db_session):
        """测试创建交易

        TC-MODEL-201: 应该能够创建交易实例
        """
        # 先创建策略和回测
        strategy = Strategy(
            name="测试策略",
            code="code"
        )
        db_session.add(strategy)
        db_session.commit()

        backtest = Backtest(
            strategy_id=strategy.id,
            symbol="600000.SH",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            initial_capital=Decimal("1000000"),
            commission=Decimal("0.0003")
        )
        db_session.add(backtest)
        db_session.commit()

        # 创建交易
        trade = Trade(
            backtest_id=backtest.id,
            symbol="600000.SH",
            side="buy",
            price=Decimal("10.5"),
            quantity=100,
            timestamp=datetime(2024, 1, 1, 10, 30)
        )

        db_session.add(trade)
        db_session.commit()

        assert trade.id is not None
        assert trade.side == "buy"
        assert trade.quantity == 100

    def test_trade_required_fields(self, db_session):
        """测试交易必填字段

        TC-MODEL-202: backtest_id, symbol, side 等是必填字段
        """
        # 先创建策略和回测
        strategy = Strategy(
            name="测试策略",
            code="code"
        )
        db_session.add(strategy)
        db_session.commit()

        backtest = Backtest(
            strategy_id=strategy.id,
            symbol="600000.SH",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            initial_capital=Decimal("1000000"),
            commission=Decimal("0.0003")
        )
        db_session.add(backtest)
        db_session.commit()

        # 缺少必填字段应该失败
        with pytest.raises(Exception):
            trade = Trade(backtest_id=backtest.id)
            db_session.add(trade)
            db_session.commit()

    def test_trade_backtest_relationship(self, db_session):
        """测试交易与回测的关系

        TC-MODEL-203: 交易应该关联到回测
        """
        strategy = Strategy(
            name="测试策略",
            code="code"
        )
        db_session.add(strategy)
        db_session.commit()

        backtest = Backtest(
            strategy_id=strategy.id,
            symbol="600000.SH",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            initial_capital=Decimal("1000000"),
            commission=Decimal("0.0003")
        )
        db_session.add(backtest)
        db_session.commit()

        trade = Trade(
            backtest_id=backtest.id,
            symbol="600000.SH",
            side="buy",
            price=Decimal("10.5"),
            quantity=100,
            timestamp=datetime.now()
        )

        db_session.add(trade)
        db_session.commit()

        assert trade.backtest_id == backtest.id

    def test_trade_side_values(self, db_session):
        """测试交易方向

        TC-MODEL-204: side 应该是 "buy" 或 "sell"
        """
        strategy = Strategy(
            name="测试策略",
            code="code"
        )
        db_session.add(strategy)
        db_session.commit()

        backtest = Backtest(
            strategy_id=strategy.id,
            symbol="600000.SH",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            initial_capital=Decimal("1000000"),
            commission=Decimal("0.0003")
        )
        db_session.add(backtest)
        db_session.commit()

        # 测试买入
        buy_trade = Trade(
            backtest_id=backtest.id,
            symbol="600000.SH",
            side="buy",
            price=Decimal("10.5"),
            quantity=100,
            timestamp=datetime.now()
        )
        db_session.add(buy_trade)

        # 测试卖出
        sell_trade = Trade(
            backtest_id=backtest.id,
            symbol="600000.SH",
            side="sell",
            price=Decimal("11.0"),
            quantity=100,
            timestamp=datetime.now()
        )
        db_session.add(sell_trade)
        db_session.commit()

        assert buy_trade.side == "buy"
        assert sell_trade.side == "sell"

    def test_backtest_trades_cascade(self, db_session):
        """测试回测删除时交易的级联删除

        TC-MODEL-205: 删除回测应该删除相关交易
        """
        strategy = Strategy(
            name="测试策略",
            code="code"
        )
        db_session.add(strategy)
        db_session.commit()

        backtest = Backtest(
            strategy_id=strategy.id,
            symbol="600000.SH",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            initial_capital=Decimal("1000000"),
            commission=Decimal("0.0003")
        )
        db_session.add(backtest)
        db_session.commit()

        trade = Trade(
            backtest_id=backtest.id,
            symbol="600000.SH",
            side="buy",
            price=Decimal("10.5"),
            quantity=100,
            timestamp=datetime.now()
        )
        db_session.add(trade)
        db_session.commit()
        trade_id = trade.id

        # 删除回测
        db_session.delete(backtest)
        db_session.commit()

        # 交易应该被级联删除
        deleted_trade = db_session.query(Trade).filter(
            Trade.id == trade_id
        ).first()

        assert deleted_trade is None

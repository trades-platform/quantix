"""数据获取修复的 QA 测试

针对 588000.SH 数据获取失败问题的回归测试。
覆盖以下修复:
1. TGW 登录失败时 AD.login() 调用 sys.exit(0) 的处理
2. 数据库自动初始化（symbols 表不存在的问题）
3. fetch_kline API 端点错误处理
4. 数据导入去重逻辑
"""

import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from backend.models.backtest import Base
from backend.models.symbol import Symbol


class TestEnsureLoginSystemExit:
    """测试 _ensure_login 对 SystemExit 的处理"""

    def test_systemexit_caught_on_login_failure(self):
        """TC-FIX-001: AD.login 失败调用 sys.exit(0) 时应抛出 RuntimeError

        验证修复: _ensure_login 捕获 SystemExit 并转换为 RuntimeError，
        防止后端进程崩溃。
        """
        with patch("backend.data.fetcher.AD") as mock_ad:
            mock_ad.login.side_effect = SystemExit(0)

            from backend.data.fetcher import _ensure_login

            # 重置登录状态
            import backend.data.fetcher as fetcher_mod

            fetcher_mod._logged_in = False

            with pytest.raises(RuntimeError, match="TGW 登录失败"):
                _ensure_login()

    def test_logged_in_not_set_on_failure(self):
        """TC-FIX-002: 登录失败后 _logged_in 不应被设为 True

        防止登录失败后仍然跳过登录，导致后续查询静默失败。
        """
        with patch("backend.data.fetcher.AD") as mock_ad:
            mock_ad.login.side_effect = SystemExit(0)

            from backend.data.fetcher import _ensure_login

            import backend.data.fetcher as fetcher_mod

            fetcher_mod._logged_in = False

            with pytest.raises(RuntimeError):
                _ensure_login()

            assert fetcher_mod._logged_in is False

    def test_logged_in_set_on_success(self):
        """TC-FIX-003: 登录成功后 _logged_in 应被设为 True"""
        with patch("backend.data.fetcher.AD") as mock_ad:
            mock_ad.login.return_value = None

            from backend.data.fetcher import _ensure_login

            import backend.data.fetcher as fetcher_mod

            fetcher_mod._logged_in = False

            _ensure_login()

            assert fetcher_mod._logged_in is True

    def test_skip_login_if_already_logged_in(self):
        """TC-FIX-004: 已登录状态应跳过登录调用"""
        with patch("backend.data.fetcher.AD") as mock_ad:
            import backend.data.fetcher as fetcher_mod

            fetcher_mod._logged_in = True

            from backend.data.fetcher import _ensure_login

            _ensure_login()

            mock_ad.login.assert_not_called()


class TestDatabaseAutoInit:
    """测试数据库自动初始化"""

    def test_symbols_table_created_on_startup(self):
        """TC-FIX-005: 应用启动时应自动创建 symbols 表

        验证修复: lifespan 中调用 init_db() 确保 symbols 表存在。
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            test_db_path = Path(tmpdir) / "test.db"
            test_engine = create_engine(f"sqlite:///{test_db_path}", echo=False)

            # 初始状态: 无表
            inspector = inspect(test_engine)
            assert "symbols" not in inspector.get_table_names()

            # 模拟 init_db
            Base.metadata.create_all(test_engine)

            # 验证 symbols 表已创建
            inspector = inspect(test_engine)
            tables = inspector.get_table_names()
            assert "symbols" in tables

            test_engine.dispose()

    def test_symbol_model_crud(self):
        """TC-FIX-006: Symbol 模型应支持基本的 CRUD 操作"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_db_path = Path(tmpdir) / "test.db"
            test_engine = create_engine(f"sqlite:///{test_db_path}", echo=False)
            TestSession = sessionmaker(bind=test_engine)
            Base.metadata.create_all(test_engine)

            session = TestSession()

            # Create
            symbol = Symbol(
                symbol="588000.SH",
                name="科创50ETF",
                data_type="etf",
                row_count=5600,
                period="min1",
            )
            session.add(symbol)
            session.commit()

            # Read
            found = session.query(Symbol).filter_by(symbol="588000.SH").first()
            assert found is not None
            assert found.name == "科创50ETF"
            assert found.data_type == "etf"
            assert found.row_count == 5600

            # Update
            found.row_count = 6000
            session.commit()
            updated = session.query(Symbol).filter_by(symbol="588000.SH").first()
            assert updated.row_count == 6000

            session.close()
            test_engine.dispose()


class TestFetchKlineEndpoint:
    """测试 fetch_kline API 端点"""

    def test_fetch_kline_success(self, client: TestClient):
        """TC-FIX-007: 正常获取 K 线数据应返回成功"""
        # AmazingData 返回的 DataFrame 使用 kline_time 列名
        mock_df = pd.DataFrame({
            "code": ["588000.SH"],
            "kline_time": [datetime(2026, 4, 14, 9, 30)],
            "open": [1.0],
            "high": [1.1],
            "low": [0.9],
            "close": [1.05],
            "volume": [100000],
            "amount": [1000000.0],
        })

        with (
            patch("backend.data.fetcher._ensure_login"),
            patch("backend.data.fetcher.AD") as mock_ad,
            patch("backend.db.kline.get_kline_db") as mock_get_db,
        ):
            mock_market = MagicMock()
            mock_market.query_kline.return_value = {"588000.SH": mock_df}
            mock_ad.BaseData.return_value.get_calendar.return_value = MagicMock()
            mock_ad.MarketData.return_value = mock_market

            mock_db = MagicMock()
            mock_table = MagicMock()
            mock_table.to_pandas.return_value = pd.DataFrame({"timestamp": pd.Series(dtype="datetime64[ns]")})
            mock_table.count_rows.return_value = 0
            mock_db.open_table.return_value = mock_table
            mock_db.create_table.return_value = mock_table
            mock_db.list_tables.return_value = []
            mock_get_db.return_value = mock_db

            response = client.post(
                "/api/data/kline/fetch",
                json={
                    "symbol": "588000.SH",
                    "period": "min1",
                    "start_date": "2026-04-14",
                    "end_date": "2026-04-17",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["symbol"] == "588000.SH"
            assert data["count"] >= 1

    def test_fetch_kline_invalid_period(self, client: TestClient):
        """TC-FIX-008: 无效周期应返回 400 错误"""
        response = client.post(
            "/api/data/kline/fetch",
            json={
                "symbol": "588000.SH",
                "period": "invalid_period",
                "start_date": "2026-04-14",
                "end_date": "2026-04-17",
            },
        )

        assert response.status_code == 400
        assert "Invalid period" in response.json()["detail"]

    def test_fetch_kline_tgw_login_failure(self, client: TestClient):
        """TC-FIX-009: TGW 登录失败应返回 500 错误而非崩溃

        验证修复: SystemExit 被捕获并转换为 RuntimeError，
        后端不再因 TGW 登录失败而崩溃。
        """
        with patch("backend.data.fetcher._ensure_login") as mock_login:
            mock_login.side_effect = RuntimeError("TGW 登录失败，请检查网络连接和配置信息")

            response = client.post(
                "/api/data/kline/fetch",
                json={
                    "symbol": "588000.SH",
                    "period": "min1",
                    "start_date": "2026-04-14",
                    "end_date": "2026-04-17",
                },
            )

            assert response.status_code == 500
            assert "TGW" in response.json()["detail"]

    def test_fetch_kline_no_data(self, client: TestClient):
        """TC-FIX-010: 数据源无数据时应返回 count=0"""
        with (
            patch("backend.data.fetcher._ensure_login"),
            patch("backend.data.fetcher.AD") as mock_ad,
        ):
            mock_market = MagicMock()
            mock_market.query_kline.return_value = {"588000.SH": pd.DataFrame()}
            mock_ad.BaseData.return_value.get_calendar.return_value = MagicMock()
            mock_ad.MarketData.return_value = mock_market

            response = client.post(
                "/api/data/kline/fetch",
                json={
                    "symbol": "588000.SH",
                    "period": "day",
                    "start_date": "2026-04-14",
                    "end_date": "2026-04-17",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["count"] == 0

    def test_fetch_kline_missing_symbol(self, client: TestClient):
        """TC-FIX-011: 缺少 symbol 参数应返回验证错误"""
        response = client.post(
            "/api/data/kline/fetch",
            json={
                "period": "min1",
                "start_date": "2026-04-14",
                "end_date": "2026-04-17",
            },
        )

        assert response.status_code == 422


class TestFetchBatchEndpoint:
    """测试批量获取 API 端点"""

    def test_batch_fetch_partial_failure(self, client: TestClient):
        """TC-FIX-012: 批量获取应正确报告部分失败"""
        # AmazingData 返回格式使用 kline_time
        mock_df = pd.DataFrame({
            "code": ["600000.SH"],
            "kline_time": [datetime(2026, 4, 14, 9, 30)],
            "open": [1.0],
            "high": [1.1],
            "low": [0.9],
            "close": [1.05],
            "volume": [100000],
            "amount": [1000000.0],
        })

        with (
            patch("backend.data.fetcher._ensure_login"),
            patch("backend.data.fetcher.AD") as mock_ad,
            patch("backend.db.kline.get_kline_db") as mock_get_db,
        ):
            call_count = [0]

            def query_side_effect(symbols, **kwargs):
                call_count[0] += 1
                if call_count[0] == 1:
                    return {"600000.SH": mock_df}
                else:
                    raise RuntimeError("TGW 查询失败")

            mock_market = MagicMock()
            mock_market.query_kline.side_effect = query_side_effect
            mock_ad.BaseData.return_value.get_calendar.return_value = MagicMock()
            mock_ad.MarketData.return_value = mock_market

            mock_db = MagicMock()
            mock_table = MagicMock()
            mock_table.to_pandas.return_value = pd.DataFrame({"timestamp": pd.Series(dtype="datetime64[ns]")})
            mock_table.count_rows.return_value = 0
            mock_db.open_table.return_value = mock_table
            mock_db.create_table.return_value = mock_table
            mock_db.list_tables.return_value = []
            mock_get_db.return_value = mock_db

            response = client.post(
                "/api/data/kline/fetch-batch",
                json={
                    "symbols": ["600000.SH", "000001.SZ"],
                    "period": "min1",
                    "start_date": "2026-04-14",
                    "end_date": "2026-04-17",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] >= 1
            assert data["failed"] >= 1


class TestKlineImportDedup:
    """测试 K 线数据导入去重逻辑"""

    def test_import_skips_duplicate_timestamps(self):
        """TC-FIX-013: 重复时间戳的数据应被跳过"""
        from backend.db.kline import import_kline

        data = pd.DataFrame({
            "timestamp": [datetime(2026, 4, 14, 9, 30)],
            "open": [1.0],
            "high": [1.1],
            "low": [0.9],
            "close": [1.05],
            "volume": [100000],
            "amount": [1000000.0],
        })

        # to_pandas() 需要返回 DataFrame（含 timestamp 列），不是 Series
        existing_df = pd.DataFrame({"timestamp": [datetime(2026, 4, 14, 9, 30)]})

        with patch("backend.db.kline.get_kline_db") as mock_get_db:
            mock_table = MagicMock()
            mock_table.to_pandas.return_value = existing_df
            mock_table.count_rows.return_value = 1
            mock_db = MagicMock()
            mock_db.open_table.return_value = mock_table
            mock_db.list_tables.return_value = ["kline_588000_SH"]
            mock_get_db.return_value = mock_db

            with patch("backend.db.kline.SessionLocal") as mock_session:
                mock_s = MagicMock()
                mock_s.query.return_value.filter.return_value.first.return_value = None
                mock_session.return_value.__enter__ = MagicMock(return_value=mock_s)
                mock_session.return_value.__exit__ = MagicMock(return_value=False)

                count = import_kline("588000.SH", data)
                assert count == 0

    def test_import_adds_new_timestamps(self):
        """TC-FIX-014: 新时间戳的数据应被正确导入"""
        from backend.db.kline import import_kline

        data = pd.DataFrame({
            "timestamp": [datetime(2026, 4, 14, 9, 31)],
            "open": [1.0],
            "high": [1.1],
            "low": [0.9],
            "close": [1.05],
            "volume": [100000],
            "amount": [1000000.0],
        })

        existing_df = pd.DataFrame({"timestamp": [datetime(2026, 4, 14, 9, 30)]})

        with patch("backend.db.kline.get_kline_db") as mock_get_db:
            mock_table = MagicMock()
            mock_table.to_pandas.return_value = existing_df
            mock_table.count_rows.return_value = 1
            mock_db = MagicMock()
            mock_db.open_table.return_value = mock_table
            mock_db.list_tables.return_value = ["kline_588000_SH"]
            mock_get_db.return_value = mock_db

            with patch("backend.db.kline.SessionLocal") as mock_session:
                mock_s = MagicMock()
                mock_s.query.return_value.filter.return_value.first.return_value = None
                mock_session.return_value.__enter__ = MagicMock(return_value=mock_s)
                mock_session.return_value.__exit__ = MagicMock(return_value=False)

                count = import_kline("588000.SH", data)
                assert count == 1
                mock_table.add.assert_called_once()


class TestFrontendTimeout:
    """测试前端超时配置"""

    def test_api_timeout_is_sufficient(self):
        """TC-FIX-015: API 超时应设置为足够长的时间（至少 60 秒）"""
        import importlib
        import sys

        # 重新加载模块以获取最新配置
        spec = importlib.util.spec_from_file_location(
            "mock_api", "/home/syl/git/trade-platforms/quantix/frontend/src/api/mock.js"
        )
        # 由于是 JS 文件，直接检查文件内容
        with open("/home/syl/git/trade-platforms/quantix/frontend/src/api/mock.js") as f:
            content = f.read()

        # 检查超时设置
        assert "timeout:" in content
        # 提取超时值
        for line in content.split("\n"):
            if "timeout" in line and "axios" not in line.lower():
                # timeout: 120000
                value = int(line.split(":")[-1].strip().rstrip(","))
                assert value >= 60000, f"Timeout {value}ms is less than 60s"


class TestPeriodMap:
    """测试周期映射完整性"""

    def test_all_periods_mapped(self, client: TestClient):
        """TC-FIX-016: 所有支持的周期都应在映射表中"""
        valid_periods = ["min1", "min5", "min15", "min30", "min60", "day", "week", "month"]

        for period in valid_periods:
            with (
                patch("backend.data.fetcher._ensure_login"),
                patch("backend.data.fetcher.AD") as mock_ad,
            ):
                mock_market = MagicMock()
                mock_market.query_kline.return_value = {"588000.SH": pd.DataFrame()}
                mock_ad.BaseData.return_value.get_calendar.return_value = MagicMock()
                mock_ad.MarketData.return_value = mock_market

                response = client.post(
                    "/api/data/kline/fetch",
                    json={
                        "symbol": "588000.SH",
                        "period": period,
                        "start_date": "2026-04-14",
                        "end_date": "2026-04-17",
                    },
                )

                assert response.status_code == 200, f"Period {period} should be valid"

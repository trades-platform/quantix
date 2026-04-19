"""get_market_data 统一接口测试"""

from datetime import datetime
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

from backend.db.kline import get_market_data


@pytest.fixture
def mock_kline_data():
    """模拟 K 线数据"""
    return pd.DataFrame({
        "timestamp": pd.date_range("2024-01-02 09:30", periods=240, freq="min"),
        "open": [10.0] * 240,
        "high": [10.5] * 240,
        "low": [9.5] * 240,
        "close": [10.2 + i * 0.001 for i in range(240)],
        "volume": [1000] * 240,
        "amount": [10000.0] * 240,
    })


@pytest.fixture
def mock_factor_data():
    """模拟因子数据"""
    return pd.DataFrame({
        "timestamp": pd.to_datetime(["2024-01-02"]),
        "factor": [1.0],
    })


class TestGetMarketDataBasic:
    """基础功能测试"""

    @patch("backend.db.factor._query_factor")
    @patch("backend.db.kline._query_kline_batch")
    def test_basic_query(self, mock_batch, mock_factor, mock_kline_data):
        """基本查询返回数据"""
        mock_batch.return_value = {"600000.SH": mock_kline_data}
        mock_factor.return_value = pd.DataFrame(columns=["timestamp", "factor"])

        result = get_market_data("600000.SH", datetime(2024, 1, 2), datetime(2024, 1, 2))
        assert "600000.SH" in result
        assert len(result["600000.SH"]) > 0

    @patch("backend.db.factor._query_factor")
    @patch("backend.db.kline._query_kline_batch")
    def test_string_symbol_wrapped(self, mock_batch, mock_factor, mock_kline_data):
        """字符串 symbol 自动包装为列表"""
        mock_batch.return_value = {"600000.SH": mock_kline_data}
        mock_factor.return_value = pd.DataFrame(columns=["timestamp", "factor"])

        result = get_market_data("600000.SH")
        mock_batch.assert_called_once_with(["600000.SH"], None, None)

    @patch("backend.db.factor._query_factor")
    @patch("backend.db.kline._query_kline_batch")
    def test_list_symbols(self, mock_batch, mock_factor, mock_kline_data):
        """列表 symbols 直接传递"""
        mock_batch.return_value = {"600000.SH": mock_kline_data, "000001.SZ": mock_kline_data}
        mock_factor.return_value = pd.DataFrame(columns=["timestamp", "factor"])

        result = get_market_data(["600000.SH", "000001.SZ"])
        mock_batch.assert_called_once_with(["600000.SH", "000001.SZ"], None, None)


class TestGetMarketDataAdjust:
    """复权测试"""

    @patch("backend.db.factor._query_factor")
    @patch("backend.db.kline._query_kline_batch")
    def test_adjust_none_skips_factor(self, mock_batch, mock_factor, mock_kline_data):
        """adjust=none 不查询因子"""
        mock_batch.return_value = {"600000.SH": mock_kline_data}

        result = get_market_data("600000.SH", adjust="none")
        mock_factor.assert_not_called()

    @patch("backend.db.factor._query_factor")
    @patch("backend.db.kline._query_kline_batch")
    def test_adjust_hfq_queries_factor(self, mock_batch, mock_factor, mock_kline_data, mock_factor_data):
        """adjust=hfq 查询并应用因子"""
        mock_batch.return_value = {"600000.SH": mock_kline_data}
        mock_factor.return_value = mock_factor_data

        result = get_market_data("600000.SH", adjust="hfq")
        mock_factor.assert_called_once_with("600000.SH")

    def test_adjust_invalid_raises(self):
        """无效 adjust 参数抛出异常"""
        with pytest.raises(ValueError, match="Invalid adjust"):
            get_market_data("600000.SH", adjust="invalid")


class TestGetMarketDataPeriod:
    """周期参数测试"""

    @patch("backend.db.factor._query_factor")
    @patch("backend.db.kline._query_kline_batch")
    def test_period_1min_no_resample(self, mock_batch, mock_factor, mock_kline_data):
        """period=1min 不做重采样"""
        mock_batch.return_value = {"600000.SH": mock_kline_data}
        mock_factor.return_value = pd.DataFrame(columns=["timestamp", "factor"])

        result = get_market_data("600000.SH", period="1min")
        assert len(result["600000.SH"]) == len(mock_kline_data)

    @patch("backend.db.factor._query_factor")
    @patch("backend.db.kline._query_kline_batch")
    def test_period_5min_resamples(self, mock_batch, mock_factor, mock_kline_data):
        """period=5min 做重采样"""
        mock_batch.return_value = {"600000.SH": mock_kline_data}
        mock_factor.return_value = pd.DataFrame(columns=["timestamp", "factor"])

        result = get_market_data("600000.SH", period="5min")
        assert len(result["600000.SH"]) < len(mock_kline_data)

    @patch("backend.db.factor._query_factor")
    @patch("backend.db.kline._query_kline_batch")
    def test_period_1D_resamples(self, mock_batch, mock_factor, mock_kline_data):
        """period=1D 合成日线"""
        mock_batch.return_value = {"600000.SH": mock_kline_data}
        mock_factor.return_value = pd.DataFrame(columns=["timestamp", "factor"])

        result = get_market_data("600000.SH", period="1D")
        assert len(result["600000.SH"]) == 1


class TestGetMarketDataNoData:
    """无数据场景"""

    @patch("backend.db.kline._query_kline_batch")
    def test_no_data_returns_empty(self, mock_batch):
        """无数据返回空字典"""
        mock_batch.return_value = {}
        result = get_market_data("999999.SH", datetime(2024, 1, 1), datetime(2024, 1, 2))
        assert "999999.SH" not in result

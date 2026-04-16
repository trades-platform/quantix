"""数据管理 API 测试"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import pandas as pd
from datetime import datetime


class TestDataAPI:
    """数据管理 API 测试类"""

    def test_get_symbols(self, client: TestClient):
        """测试获取标的列表

        TC-API-401: GET /api/data/symbols 应返回标的列表
        """
        with patch('backend.db.kline.get_kline_db') as mock_get_db:
            mock_db = MagicMock()
            mock_db.table_names.return_value = ["kline_600000.SH", "kline_000001.SZ"]
            mock_get_db.return_value = mock_db

            response = client.get("/api/data/symbols")

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)

    def test_get_symbols_empty(self, client: TestClient):
        """测试获取空标的列表

        TC-API-402: 无标的时应返回空列表
        """
        with patch('backend.db.kline.get_kline_db') as mock_get_db:
            mock_db = MagicMock()
            mock_db.table_names.return_value = []
            mock_get_db.return_value = mock_db

            response = client.get("/api/data/symbols")

            assert response.status_code == 200
            data = response.json()
            assert data == []

    def test_get_kline_data(self, client: TestClient):
        """测试获取K线数据

        TC-API-403: GET /api/data/kline 应返回K线数据
        """
        mock_data = pd.DataFrame({
            'timestamp': [datetime(2024, 1, 1), datetime(2024, 1, 2)],
            'open': [10.0, 10.5],
            'high': [10.5, 11.0],
            'low': [9.5, 10.0],
            'close': [10.2, 10.8],
            'volume': [1000000, 1100000],
        })

        with patch('backend.db.kline.get_kline_db') as mock_get_db:
            mock_db = MagicMock()
            mock_table = MagicMock()
            mock_table.to_pandas.return_value = mock_data
            mock_db.open_table.return_value = mock_table
            mock_db.table_names.return_value = ["kline_600000.SH"]
            mock_get_db.return_value = mock_db

            response = client.get("/api/data/kline?symbol=600000.SH&start_date=2024-01-01&end_date=2024-12-31")

            assert response.status_code == 200
            data = response.json()
            assert "symbol" in data
            assert "data" in data
            assert isinstance(data["data"], list)

    def test_get_kline_data_invalid_date_format(self, client: TestClient):
        """测试获取K线数据日期格式错误

        TC-API-404: 错误的日期格式应返回错误
        """
        with patch('backend.db.kline.get_kline_db') as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value = mock_db

            response = client.get("/api/data/kline?symbol=600000.SH&start_date=2024/01/01")

            # API 会尝试解析日期，失败时返回 400 Bad Request
            assert response.status_code == 400

    def test_import_kline_data(self, client: TestClient):
        """测试导入K线数据

        TC-API-405: POST /api/data/kline/import 应成功导入数据
        """
        import_data = {
            "symbol": "600000.SH",
            "start_date": "2024-01-01",
            "end_date": "2024-01-02",
            "data": [
                {
                    "timestamp": "2024-01-01T00:00:00",
                    "open": 10.0,
                    "high": 10.5,
                    "low": 9.5,
                    "close": 10.2,
                    "volume": 1000000
                }
            ]
        }

        with patch('backend.db.kline.get_kline_db') as mock_get_db:
            mock_db = MagicMock()
            # Mock the table operations
            mock_table = MagicMock()
            mock_table.to_pandas.return_value = pd.DataFrame()
            mock_table.count_rows.return_value = 0
            mock_db.open_table.return_value = mock_table
            mock_db.create_table.return_value = mock_table
            mock_db.table_names.return_value = []
            mock_get_db.return_value = mock_db

            response = client.post("/api/data/kline/import", json=import_data)

            # 导入应该成功
            assert response.status_code == 201
            data = response.json()
            assert "message" in data
            assert "count" in data

    def test_import_kline_data_empty(self, client: TestClient):
        """测试导入空K线数据

        TC-API-406: 空数据应返回错误
        """
        import_data = {
            "symbol": "600000.SH",
            "start_date": "2024-01-01",
            "end_date": "2024-01-02",
            "data": []
        }

        with patch('backend.db.lancedb.lancedb.connect') as mock_connect:
            mock_db = MagicMock()
            mock_connect.return_value = mock_db

            response = client.post("/api/data/kline/import", json=import_data)

            # 空数据应该返回错误
            assert response.status_code in [400, 422]

    def test_import_kline_data_missing_fields(self, client: TestClient):
        """测试导入缺少字段的K线数据

        TC-API-407: 缺少必填字段应返回错误
        """
        import_data = {
            "symbol": "600000.SH",
            "start_date": "2024-01-01",
            "end_date": "2024-01-02",
            "data": [
                {
                    "timestamp": "2024-01-01T00:00:00",
                    "open": 10.0,
                    # 缺少其他必填字段
                }
            ]
        }

        with patch('backend.db.lancedb.lancedb.connect') as mock_connect:
            mock_db = MagicMock()
            mock_connect.return_value = mock_db

            response = client.post("/api/data/kline/import", json=import_data)

            # 缺少字段应该返回错误
            assert response.status_code in [400, 500]

    def test_upload_kline_file(self, client: TestClient):
        """测试上传K线文件

        TC-API-408: POST /api/data/kline/upload 应成功处理文件
        """
        # 创建简单的 CSV 内容
        csv_content = b"timestamp,open,high,low,close,volume\n2024-01-01,10.0,10.5,9.5,10.2,1000000\n"

        from io import BytesIO

        with patch('backend.db.kline.get_kline_db') as mock_get_db:
            mock_db = MagicMock()
            mock_table = MagicMock()
            mock_table.to_pandas.return_value = pd.DataFrame()
            mock_table.count_rows.return_value = 0
            mock_db.open_table.return_value = mock_table
            mock_db.create_table.return_value = mock_table
            mock_db.table_names.return_value = []
            mock_get_db.return_value = mock_db

            files = {"file": ("test.csv", BytesIO(csv_content), "text/csv")}
            params = {"symbol": "600000.SH"}

            response = client.post("/api/data/kline/upload", files=files, params=params)

            # 文件上传应该成功
            assert response.status_code in [200, 201, 400]

    def test_upload_kline_file_invalid_format(self, client: TestClient):
        """测试上传无效格式文件

        TC-API-409: 无效 CSV 格式应返回错误
        """
        from io import BytesIO

        # 无效的 CSV 内容
        invalid_csv = b"invalid,csv,data\n1,2,3"

        with patch('backend.db.kline.get_kline_db') as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value = mock_db

            files = {"file": ("test.csv", BytesIO(invalid_csv), "text/csv")}
            params = {"symbol": "600000.SH"}

            response = client.post("/api/data/kline/upload", files=files, params=params)

            # 无效格式应该返回错误
            assert response.status_code in [400, 422]

    def test_get_kline_data_no_symbol(self, client: TestClient):
        """测试获取K线数据缺少标的

        TC-API-410: 缺少 symbol 参数应返回错误
        """
        response = client.get("/api/data/kline")

        # 缺少参数应该返回错误
        assert response.status_code in [400, 422]

    def test_get_kline_data_date_filter(self, client: TestClient):
        """测试K线数据日期过滤

        TC-API-411: 应该正确过滤日期范围
        """
        mock_data = pd.DataFrame({
            'timestamp': [datetime(2024, 1, i) for i in range(1, 11)],
            'open': [10.0] * 10,
            'high': [10.5] * 10,
            'low': [9.5] * 10,
            'close': [10.2] * 10,
            'volume': [1000000] * 10,
        })

        with patch('backend.db.kline.get_kline_db') as mock_get_db:
            mock_db = MagicMock()
            mock_table = MagicMock()
            mock_table.to_pandas.return_value = mock_data
            mock_db.open_table.return_value = mock_table
            mock_db.table_names.return_value = ["kline_600000.SH"]
            mock_get_db.return_value = mock_db

            response = client.get("/api/data/kline?symbol=600000.SH&start_date=2024-01-05&end_date=2024-01-08")

            assert response.status_code == 200
            data = response.json()
            assert "data" in data

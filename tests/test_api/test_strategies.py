"""策略管理 API 测试"""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime


class TestStrategiesAPI:
    """策略管理 API 测试类"""

    def test_create_strategy(self, client: TestClient, sample_strategy):
        """测试创建策略

        TC-API-201: POST 创建有效策略应返回策略对象, 201
        """
        response = client.post("/api/strategies", json=sample_strategy)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == sample_strategy["name"]
        assert data["description"] == sample_strategy["description"]
        assert data["code"] == sample_strategy["code"]
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_strategy_missing_fields(self, client: TestClient):
        """测试创建缺少必填字段的策略

        TC-API-202: POST 创建无效策略应返回验证错误, 422
        """
        # 缺少 code 字段
        invalid_strategy = {
            "name": "测试策略",
            "description": "缺少代码"
        }

        response = client.post("/api/strategies", json=invalid_strategy)

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_create_strategy_empty_name(self, client: TestClient):
        """测试创建空名称的策略

        TC-API-203: 空名称应该返回验证错误
        """
        invalid_strategy = {
            "name": "",
            "code": "def handle_bar(context): return []"
        }

        response = client.post("/api/strategies", json=invalid_strategy)

        assert response.status_code == 422

    def test_list_strategies_empty(self, client: TestClient):
        """测试获取空策略列表

        TC-API-204: GET 获取策略列表应返回空数组, 200
        """
        response = client.get("/api/strategies")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_list_strategies(self, client: TestClient, sample_strategy):
        """测试获取策略列表

        TC-API-205: GET 获取策略列表应返回策略数组, 200
        """
        # 创建两个策略
        client.post("/api/strategies", json=sample_strategy)
        client.post("/api/strategies", json={
            "name": "另一个策略",
            "description": "测试",
            "code": "def handle_bar(context): return []"
        })

        response = client.get("/api/strategies")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 2

    def test_get_strategy_exists(self, client: TestClient, sample_strategy):
        """测试获取存在的策略

        TC-API-206: GET 获取存在的策略应返回策略对象, 200
        """
        # 先创建策略
        create_response = client.post("/api/strategies", json=sample_strategy)
        strategy_id = create_response.json()["id"]

        # 获取策略
        response = client.get(f"/api/strategies/{strategy_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == strategy_id
        assert data["name"] == sample_strategy["name"]

    def test_get_strategy_not_found(self, client: TestClient):
        """测试获取不存在的策略

        TC-API-207: GET 获取不存在的策略应返回 404
        """
        response = client.get("/api/strategies/99999")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    def test_update_strategy(self, client: TestClient, sample_strategy):
        """测试更新策略

        TC-API-208: PUT 更新策略应返回更新后的策略, 200
        """
        # 先创建策略
        create_response = client.post("/api/strategies", json=sample_strategy)
        strategy_id = create_response.json()["id"]

        # 更新策略
        update_data = {
            "name": "更新后的策略名称",
            "description": "更新后的描述"
        }
        response = client.put(f"/api/strategies/{strategy_id}", json=update_data)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "更新后的策略名称"
        assert data["description"] == "更新后的描述"
        # code 不应该被改变
        assert data["code"] == sample_strategy["code"]

    def test_update_strategy_not_found(self, client: TestClient):
        """测试更新不存在的策略

        TC-API-209: PUT 更新不存在的策略应返回 404
        """
        update_data = {
            "name": "更新"
        }
        response = client.put("/api/strategies/99999", json=update_data)

        assert response.status_code == 404

    def test_delete_strategy(self, client: TestClient, sample_strategy):
        """测试删除策略

        TC-API-210: DELETE 删除策略应返回 204
        """
        # 先创建策略
        create_response = client.post("/api/strategies", json=sample_strategy)
        strategy_id = create_response.json()["id"]

        # 删除策略
        response = client.delete(f"/api/strategies/{strategy_id}")

        assert response.status_code == 204

        # 验证策略已被删除
        get_response = client.get(f"/api/strategies/{strategy_id}")
        assert get_response.status_code == 404

    def test_delete_strategy_not_found(self, client: TestClient):
        """测试删除不存在的策略

        TC-API-211: DELETE 删除不存在的策略应返回 404
        """
        response = client.delete("/api/strategies/99999")

        assert response.status_code == 404

    def test_strategy_partial_update(self, client: TestClient, sample_strategy):
        """测试部分更新策略

        TC-API-212: PUT 只更新指定字段
        """
        # 先创建策略
        create_response = client.post("/api/strategies", json=sample_strategy)
        strategy_id = create_response.json()["id"]
        original_description = create_response.json()["description"]

        # 只更新名称
        update_data = {
            "name": "新名称"
        }
        response = client.put(f"/api/strategies/{strategy_id}", json=update_data)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "新名称"
        assert data["description"] == original_description  # 描述不变

    def test_strategy_update_all_fields(self, client: TestClient, sample_strategy):
        """测试更新所有字段

        TC-API-213: PUT 可以更新所有可更新字段
        """
        # 先创建策略
        create_response = client.post("/api/strategies", json=sample_strategy)
        strategy_id = create_response.json()["id"]

        # 更新所有字段
        update_data = {
            "name": "新名称",
            "description": "新描述",
            "code": "def handle_bar(context): return []"
        }
        response = client.put(f"/api/strategies/{strategy_id}", json=update_data)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "新名称"
        assert data["description"] == "新描述"
        assert data["code"] == "def handle_bar(context): return []"

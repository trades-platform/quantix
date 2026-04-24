"""标的池 API 测试"""

from fastapi.testclient import TestClient


class TestSymbolPoolsAPI:
    """标的池 API 测试类"""

    def test_symbol_pool_crud(self, client: TestClient):
        create_response = client.post(
            "/api/symbol-pools",
            json={
                "name": "etf_core",
                "description": "核心 ETF 组合",
                "symbols": ["588000.SH", "159682.SZ"],
            },
        )

        assert create_response.status_code == 201
        created = create_response.json()
        assert created["name"] == "etf_core"
        assert created["symbols"] == ["588000.SH", "159682.SZ"]

        list_response = client.get("/api/symbol-pools")
        assert list_response.status_code == 200
        assert len(list_response.json()) == 1

        get_response = client.get("/api/symbol-pools/etf_core")
        assert get_response.status_code == 200
        assert get_response.json()["description"] == "核心 ETF 组合"

        update_response = client.put(
            "/api/symbol-pools/etf_core",
            json={
                "name": "etf_growth",
                "description": "更新后的组合",
                "symbols": ["159682.SZ", "588000.SH", "588000.SH"],
            },
        )
        assert update_response.status_code == 200
        updated = update_response.json()
        assert updated["name"] == "etf_growth"
        assert updated["symbols"] == ["159682.SZ", "588000.SH"]

        delete_response = client.delete("/api/symbol-pools/etf_growth")
        assert delete_response.status_code == 204

        not_found_response = client.get("/api/symbol-pools/etf_growth")
        assert not_found_response.status_code == 404

    def test_create_symbol_pool_duplicate_name(self, client: TestClient):
        payload = {
            "name": "bank_etf",
            "description": "",
            "symbols": ["512800.SH", "515290.SH"],
        }

        first_response = client.post("/api/symbol-pools", json=payload)
        second_response = client.post("/api/symbol-pools", json=payload)

        assert first_response.status_code == 201
        assert second_response.status_code == 400
        assert "已存在" in second_response.json()["detail"]

    def test_update_symbol_pool_requires_payload(self, client: TestClient):
        create_response = client.post(
            "/api/symbol-pools",
            json={
                "name": "dividend",
                "description": "",
                "symbols": ["515180.SH"],
            },
        )

        assert create_response.status_code == 201

        update_response = client.put("/api/symbol-pools/dividend", json={})
        assert update_response.status_code == 422

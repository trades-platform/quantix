"""健康检查端点测试"""

from fastapi.testclient import TestClient


def test_health_check(client: TestClient):
    """测试健康检查端点返回正确响应

    TC-API-001: GET /api/health 应返回 {"status": "ok"}, 200
    """
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_check_response_time(client: TestClient):
    """测试健康检查响应时间

    健康检查端点应该快速响应
    """
    import time

    start_time = time.time()
    response = client.get("/api/health")
    end_time = time.time()

    assert response.status_code == 200
    # 响应时间应该小于 100ms
    assert (end_time - start_time) < 0.1

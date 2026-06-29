import pytest
from fastapi.testclient import TestClient
from app.main import app, fetcher

client = TestClient(app)

def test_get_history_endpoint():
    # 预设模拟数据
    fetcher.history_cache = {
        "BK0437": {
            "timestamps": ["09:30", "09:31"],
            "values": [0.0, 1.25]
        }
    }
    
    response = client.get("/api/sectors/history")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert "BK0437" in data["data"]
    assert data["data"]["BK0437"]["values"] == [0.0, 1.25]

def test_websocket_connection():
    # 测试 Websocket 心跳与通信逻辑
    with client.websocket_connect("/ws/capital-flow") as websocket:
        # 发送 pong
        websocket.send_json({"type": "pong"})
        # WebSocket 能够正常握手并没有异常关闭

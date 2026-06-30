import pytest
from fastapi.testclient import TestClient
from app.main import app, fetcher
from unittest.mock import AsyncMock, patch, MagicMock

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

def test_get_sector_history_endpoint():
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {
            "klines": ["2026-06-30 09:30,12345000000"]
        }
    }
    mock_client.get.return_value = mock_response
    
    with patch.object(fetcher, "get_client", return_value=mock_client):
        response = client.get("/api/sectors/history/BK0437?period=daily")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert data["data"]["timestamps"] == ["09:30"]
        assert data["data"]["values"] == [123.45]
        mock_client.get.assert_called_once()
        args, kwargs = mock_client.get.call_args
        assert kwargs["params"]["klt"] == "101"
        assert kwargs["params"]["lmt"] == "30"

def test_get_sector_history_endpoint_today():
    fetcher.history_cache = {
        "BK0437": {
            "timestamps": ["09:30", "09:31"],
            "values": [1.0, 2.5]
        }
    }
    response = client.get("/api/sectors/history/BK0437?period=1")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert data["data"]["timestamps"] == ["09:30", "09:31"]
    assert data["data"]["values"] == [1.0, 2.5]

def test_get_sector_stocks_endpoint():
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {
            "diff": [
                {
                    "f2": 15.5,
                    "f3": 2.3,
                    "f12": "600519",
                    "f14": "贵州茅台",
                    "f62": 100000000.0
                }
            ]
        }
    }
    mock_client.get.return_value = mock_response
    
    # Clear cache first to force HTTP call
    from app.main import stocks_cache
    stocks_cache.clear()
    
    with patch.object(fetcher, "get_client", return_value=mock_client):
        response = client.get("/api/sectors/BK0437/stocks")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        stocks = data["data"]["stocks"]
        assert len(stocks) == 1
        assert stocks[0]["code"] == "600519"
        assert stocks[0]["name"] == "贵州茅台"
        assert stocks[0]["price"] == 15.5
        assert stocks[0]["change_pct"] == 2.3
        assert stocks[0]["main_net_inflow"] == 1.0
        mock_client.get.assert_called_once()

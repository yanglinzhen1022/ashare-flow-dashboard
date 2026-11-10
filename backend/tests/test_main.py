import httpx
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

def test_get_sector_stocks_cache_evicts_expired_entries():
    """成功拉取后应清理超过 TTL 的过期缓存条目，保留仍有效的条目"""
    import time as time_mod
    from app.main import stocks_cache

    stocks_cache.clear()
    # 预置一个早已过期(120s前)和一个仍然新鲜(5s前)的缓存条目
    stocks_cache["BK0001"] = (time_mod.time() - 120.0, [{"code": "600000"}])
    stocks_cache["BK0002"] = (time_mod.time() - 5.0, [{"code": "600001"}])

    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": {"diff": []}}
    mock_client.get.return_value = mock_response

    try:
        with patch.object(fetcher, "get_client", return_value=mock_client):
            response = client.get("/api/sectors/BK0437/stocks")
            assert response.status_code == 200

        assert "BK0001" not in stocks_cache, "过期条目应被淘汰"
        assert "BK0002" in stocks_cache, "新鲜条目应保留"
        assert "BK0437" in stocks_cache, "新拉取条目应写入"
    finally:
        stocks_cache.clear()


def test_api_error_contract_on_fetch_failure():
    """HTTP 客户端抛异常时应返回 HTTP 200 + {code: 500, message} 错误契约（前端依赖此形状）"""
    mock_client = AsyncMock()
    mock_client.get.side_effect = httpx.ConnectError("connection refused")

    from app.main import stocks_cache
    stocks_cache.clear()

    try:
        with patch.object(fetcher, "get_client", return_value=mock_client):
            response = client.get("/api/sectors/BK0437/stocks")
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 500
            assert "connection refused" in data["message"]
            assert "stocks" not in data.get("data", {})
    finally:
        stocks_cache.clear()


def test_get_stock_intraday_endpoint():
    """个股分时端点：应调用 trends2 与分钟资金流两个接口并正确解析累计资金流"""
    mock_client = AsyncMock()

    mock_trends_resp = MagicMock()
    mock_trends_resp.status_code = 200
    mock_trends_resp.json.return_value = {
        "data": {
            "code": "600519",
            "name": "贵州茅台",
            "preClose": 1444.99,
            "trends": [
                "2026-11-10 09:30,1438.23,204,29339892.00,1438.230",
                "2026-11-10 09:31,1434.60,804,115311562.00,1435.034"
            ]
        }
    }

    mock_fflow_resp = MagicMock()
    mock_fflow_resp.status_code = 200
    mock_fflow_resp.json.return_value = {
        "data": {
            "klines": [
                "2026-11-10 09:30,100000000.0,1000000.0,2000000.0,30000000.0,70000000.0",
                "2026-11-10 09:31,100000000.0,1000000.0,2000000.0,30000000.0,70000000.0"
            ]
        }
    }
    mock_client.get.side_effect = [mock_trends_resp, mock_fflow_resp]

    from app.main import stock_detail_cache
    stock_detail_cache.clear()

    try:
        with patch.object(fetcher, "get_client", return_value=mock_client):
            response = client.get("/api/stocks/600519/intraday")
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            d = data["data"]
            assert d["name"] == "贵州茅台"
            assert d["timestamps"] == ["09:30", "09:31"]
            assert d["prices"] == [1438.23, 1434.60]
            assert d["avg_prices"] == [1438.23, 1435.034]
            assert d["last_price"] == 1434.60
            assert d["change_pct"] == -0.72  # (1434.60-1444.99)/1444.99*100
            # 今日累计主力/单型资金流 (元→亿)
            assert d["main_net_inflow"] == 2.0
            assert d["super_large_inflow"] == 1.4
            assert d["large_inflow"] == 0.6
            assert d["medium_inflow"] == 0.04
            assert d["small_inflow"] == 0.02

            # 第一个请求应为 trends2 且 secid 带沪市前缀 1.
            args1, kwargs1 = mock_client.get.call_args_list[0]
            assert "trends2/get" in args1[0]
            assert kwargs1["params"]["secid"] == "1.600519"
            # 第二个请求应为分钟资金流 fflow kline
            args2, kwargs2 = mock_client.get.call_args_list[1]
            assert "fflow/kline/get" in args2[0]
            assert kwargs2["params"]["klt"] == "1"
    finally:
        stock_detail_cache.clear()


def test_get_stock_intraday_deep_market_prefix():
    """深市股票代码 (0/3开头) 的 secid 前缀应为 0."""
    mock_client = AsyncMock()

    mock_trends_resp = MagicMock()
    mock_trends_resp.status_code = 200
    mock_trends_resp.json.return_value = {
        "data": {
            "code": "000725",
            "name": "京东方A",
            "preClose": 4.50,
            "trends": ["2026-11-10 09:30,4.51,204,100000.00,4.500"]
        }
    }
    mock_fflow_resp = MagicMock()
    mock_fflow_resp.status_code = 200
    mock_fflow_resp.json.return_value = {"data": {"klines": []}}
    mock_client.get.side_effect = [mock_trends_resp, mock_fflow_resp]

    from app.main import stock_detail_cache
    stock_detail_cache.clear()

    try:
        with patch.object(fetcher, "get_client", return_value=mock_client):
            response = client.get("/api/stocks/000725/intraday")
            assert response.status_code == 200
            args1, kwargs1 = mock_client.get.call_args_list[0]
            assert kwargs1["params"]["secid"] == "0.000725"
    finally:
        stock_detail_cache.clear()


def test_get_stock_intraday_cache_hit():
    """TTL 内重复请求应命中缓存，不再触发 HTTP 调用"""
    mock_client = AsyncMock()

    mock_trends_resp = MagicMock()
    mock_trends_resp.status_code = 200
    mock_trends_resp.json.return_value = {
        "data": {"code": "600519", "name": "贵州茅台", "preClose": 1444.99, "trends": []}
    }
    mock_fflow_resp = MagicMock()
    mock_fflow_resp.status_code = 200
    mock_fflow_resp.json.return_value = {"data": {"klines": []}}
    mock_client.get.side_effect = [mock_trends_resp, mock_fflow_resp]

    from app.main import stock_detail_cache
    stock_detail_cache.clear()

    try:
        with patch.object(fetcher, "get_client", return_value=mock_client):
            client.get("/api/stocks/600519/intraday")
            client.get("/api/stocks/600519/intraday")
            assert mock_client.get.call_count == 2, "第二次请求应命中缓存而非再次发起 HTTP"
    finally:
        stock_detail_cache.clear()


def test_get_stock_kline_endpoint():
    """个股日K端点：解析 OHLCV 数组并携带必需的 ut/end 参数"""
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {
            "code": "600519",
            "name": "贵州茅台",
            "klines": [
                "2026-05-18,1307.98,1294.98,1314.66,1291.59,49661,6594983723.00",
                "2026-05-19,1293.88,1296.28,1301.97,1289.98,43255,5719170335.00"
            ]
        }
    }
    mock_client.get.return_value = mock_response

    from app.main import stock_detail_cache
    stock_detail_cache.clear()

    try:
        with patch.object(fetcher, "get_client", return_value=mock_client):
            response = client.get("/api/stocks/600519/kline")
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            d = data["data"]
            assert d["name"] == "贵州茅台"
            assert d["timestamps"] == ["2026-05-18", "2026-05-19"]
            assert d["open"] == [1307.98, 1293.88]
            assert d["close"] == [1294.98, 1296.28]
            assert d["high"] == [1314.66, 1301.97]
            assert d["low"] == [1291.59, 1289.98]
            assert d["volume"] == [49661, 43255]
            # 报价字段: 头部行情展示依赖, 应从最后两根收盘价计算
            assert d["last_price"] == 1296.28
            assert d["change_pct"] == 0.1  # (1296.28-1294.98)/1294.98*100 ≈ 0.1

            args1, kwargs1 = mock_client.get.call_args_list[0]
            assert "kline/get" in args1[0]
            assert kwargs1["params"]["klt"] == "101"
            assert kwargs1["params"]["fqt"] == "1"
            assert kwargs1["params"]["lmt"] == "120"
            assert kwargs1["params"]["end"] == "20500101"
    finally:
        stock_detail_cache.clear()


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
        args, kwargs = mock_client.get.call_args
        assert kwargs["params"]["pz"] == "50"


def test_get_sector_stocks_endpoint_custom_limit():
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": {"diff": []}}
    mock_client.get.return_value = mock_response

    from app.main import stocks_cache
    stocks_cache.clear()

    with patch.object(fetcher, "get_client", return_value=mock_client):
        response = client.get("/api/sectors/BK0437/stocks?limit=30")
        assert response.status_code == 200
        args, kwargs = mock_client.get.call_args
        assert kwargs["params"]["pz"] == "30"


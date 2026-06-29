import pytest
from app.scheduler import DataFetcher
from app.manager import ConnectionManager
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

@pytest.mark.asyncio
async def test_data_fetch_and_formatting():
    mock_manager = AsyncMock(spec=ConnectionManager)
    fetcher = DataFetcher(mock_manager)
    
    # 模拟东财 API 返回格式
    mock_raw_response = {
        "data": {
            "diff": [
                {
                    "f12": "BK0437",
                    "f14": "半导体",
                    "f3": 2.45,
                    "f62": 1235000000.0, # 12.35 亿元
                    "f66": 810000000.0,
                    "f72": 425000000.0,
                    "f78": -215000000.0,
                    "f84": -1020000000.0
                }
            ]
        }
    }
    
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_response = MagicMock()
        mock_response.json = lambda: mock_raw_response
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        # 执行单次数据抓取与转换
        data = await fetcher.fetch_and_broadcast()
        
        assert len(data["industry"]) == 1
        item = data["industry"][0]
        assert item["code"] == "BK0437"
        assert item["name"] == "半导体"
        assert item["change_pct"] == 2.45
        assert item["main_net_inflow"] == 12.35
        assert item["super_large_inflow"] == 8.10
        assert item["large_inflow"] == 4.25
        assert item["medium_inflow"] == -2.15
        assert item["small_inflow"] == -10.20
        
        # 验证广播被触发
        mock_manager.broadcast.assert_called_once()

@pytest.mark.asyncio
async def test_data_fetch_client_reuse():
    mock_manager = AsyncMock(spec=ConnectionManager)
    fetcher = DataFetcher(mock_manager)
    
    mock_raw_response = {"data": {"diff": []}}
    
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_response = MagicMock()
        mock_response.json = lambda: mock_raw_response
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        # 第一次抓取
        assert fetcher.client is None
        await fetcher.fetch_and_broadcast()
        client1 = fetcher.client
        assert client1 is not None
        
        # 第二次抓取
        await fetcher.fetch_and_broadcast()
        client2 = fetcher.client
        assert client2 is client1  # 验证 client instance 被复用

@pytest.mark.asyncio
async def test_data_fetch_failure_no_broadcast():
    mock_manager = AsyncMock(spec=ConnectionManager)
    fetcher = DataFetcher(mock_manager)
    
    # 模拟已有历史数据
    fetcher.latest_data = {
        "timestamp": "12:00:00",
        "industry": [{"code": "BK0437", "name": "半导体"}],
        "concept": []
    }
    
    with patch("httpx.AsyncClient.get") as mock_get:
        # 模拟请求异常
        mock_get.side_effect = httpx.RequestError("Connection timeout")
        
        # 触发抓取
        data = await fetcher.fetch_and_broadcast()
        
        # 验证返回的是旧的 latest_data，没有被清空/覆盖
        assert data == {
            "timestamp": "12:00:00",
            "industry": [{"code": "BK0437", "name": "半导体"}],
            "concept": []
        }
        assert fetcher.latest_data == data
        
        # 验证没有调用 broadcast
        mock_manager.broadcast.assert_not_called()

@pytest.mark.asyncio
async def test_history_cache_cleared_on_new_day():
    mock_manager = AsyncMock(spec=ConnectionManager)
    fetcher = DataFetcher(mock_manager)
    fetcher.history_cache = {
        "BK0437": {"timestamps": ["09:30"], "values": [1.2]}
    }
    fetcher.last_date = "2026-06-28"
    
    with patch("time.strftime") as mock_strftime:
        mock_strftime.return_value = "2026-06-29"
        
        fetcher._update_history_cache("09:31", [{"code": "BK0437", "main_net_inflow": 2.5}])
        
        assert "BK0437" in fetcher.history_cache
        assert fetcher.history_cache["BK0437"]["timestamps"] == ["09:31"]
        assert fetcher.history_cache["BK0437"]["values"] == [2.5]
        assert fetcher.last_date == "2026-06-29"

def test_unsafe_dictionary_default_handling():
    mock_manager = AsyncMock(spec=ConnectionManager)
    fetcher = DataFetcher(mock_manager)
    
    bad_items = [
        {
            "f12": None,
            "f14": None,
            "f3": None,
            "f62": None,
            "f66": None,
            "f72": None,
            "f78": None,
            "f84": None
        },
        {
            "f12": "BK0437",
            "f14": "半导体",
            "f3": "-",
            "f62": "NaN",
            "f66": "123.45",
            "f72": None,
            "f78": "-",
            "f84": "NaN"
        }
    ]
    
    formatted = fetcher._format_items(bad_items)
    assert len(formatted) == 2
    
    item1 = formatted[0]
    assert item1["code"] == ""
    assert item1["name"] == ""
    assert item1["change_pct"] == 0.0
    assert item1["main_net_inflow"] == 0.0
    assert item1["super_large_inflow"] == 0.0
    assert item1["large_inflow"] == 0.0
    assert item1["medium_inflow"] == 0.0
    assert item1["small_inflow"] == 0.0

    item2 = formatted[1]
    assert item2["code"] == "BK0437"
    assert item2["name"] == "半导体"
    assert item2["change_pct"] == 0.0
    assert item2["main_net_inflow"] == 0.0
    assert item2["super_large_inflow"] == 0.0
    assert item2["large_inflow"] == 0.0
    assert item2["medium_inflow"] == 0.0
    assert item2["small_inflow"] == 0.0

@pytest.mark.asyncio
async def test_shutdown_closes_client():
    mock_manager = AsyncMock(spec=ConnectionManager)
    fetcher = DataFetcher(mock_manager)
    fetcher.client = AsyncMock()
    
    await fetcher.shutdown()
    fetcher.client.aclose.assert_called_once()

@pytest.mark.asyncio
async def test_shutdown_with_none_client():
    mock_manager = AsyncMock(spec=ConnectionManager)
    fetcher = DataFetcher(mock_manager)
    fetcher.client = None
    
    # Should not raise any error
    await fetcher.shutdown()



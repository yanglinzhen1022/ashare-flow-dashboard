import pytest
from app.scheduler import DataFetcher
from app.manager import ConnectionManager
from unittest.mock import AsyncMock, patch

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
        mock_get.return_value.json = lambda: mock_raw_response
        mock_get.return_value.status_code = 200
        
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

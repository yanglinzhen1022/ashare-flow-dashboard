import pytest
from fastapi.websockets import WebSocket
from unittest.mock import AsyncMock, MagicMock
from app.manager import ConnectionManager

@pytest.mark.asyncio
async def test_connection_lifecycle():
    manager = ConnectionManager()
    mock_ws = AsyncMock(spec=WebSocket)
    
    # 测试连接
    await manager.connect(mock_ws)
    assert mock_ws in manager.active_connections
    
    # 测试广播
    test_msg = {"type": "test", "data": "hello"}
    await manager.broadcast(test_msg)
    mock_ws.send_json.assert_called_once_with(test_msg)
    
    # 测试断开连接
    manager.disconnect(mock_ws)
    assert mock_ws not in manager.active_connections

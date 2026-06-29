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

@pytest.mark.asyncio
async def test_broadcast_failure_cleanup():
    manager = ConnectionManager()
    mock_ws_success = AsyncMock(spec=WebSocket)
    mock_ws_fail = AsyncMock(spec=WebSocket)
    mock_ws_fail.send_json.side_effect = Exception("Send failed")
    
    await manager.connect(mock_ws_success)
    await manager.connect(mock_ws_fail)
    
    assert len(manager.active_connections) == 2
    
    test_msg = {"type": "test", "data": "hello"}
    await manager.broadcast(test_msg)
    
    # The failed socket should be removed, but the successful one remains
    assert mock_ws_fail not in manager.active_connections
    assert mock_ws_success in manager.active_connections
    mock_ws_success.send_json.assert_called_once_with(test_msg)

@pytest.mark.asyncio
async def test_ping_loop():
    from unittest.mock import patch
    import asyncio
    manager = ConnectionManager()
    mock_ws = AsyncMock(spec=WebSocket)
    await manager.connect(mock_ws)
    
    sleep_count = 0
    async def mock_sleep(seconds):
        nonlocal sleep_count
        sleep_count += 1
        if sleep_count > 1:
            raise asyncio.CancelledError()

    with patch("asyncio.sleep", side_effect=mock_sleep):
        await manager.start_ping_loop()
        
    mock_ws.send_json.assert_called_once_with({"type": "ping"})

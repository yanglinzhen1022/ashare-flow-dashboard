import asyncio
from typing import List
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)

    async def start_ping_loop(self):
        while True:
            try:
                await asyncio.sleep(10)
                for connection in list(self.active_connections):
                    try:
                        await connection.send_json({"type": "ping"})
                    except Exception:
                        self.disconnect(connection)
            except asyncio.CancelledError:
                break
            except Exception:
                pass

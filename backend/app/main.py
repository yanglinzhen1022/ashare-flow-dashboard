import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from app.manager import ConnectionManager
from app.scheduler import DataFetcher

# 全局单例管理器
manager = ConnectionManager()
fetcher = DataFetcher(manager)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: 启动后台数据拉取轮询协程与心跳循环
    task = asyncio.create_task(fetcher.start_loop())
    ping_task = asyncio.create_task(manager.start_ping_loop())
    yield
    # Shutdown: 优雅关闭 HTTP 客户端并取消后台任务
    task.cancel()
    ping_task.cancel()
    try:
        await asyncio.gather(task, ping_task, return_exceptions=True)
    except asyncio.CancelledError:
        pass
    await fetcher.shutdown()

app = FastAPI(title="A-Share Capital Flow Dashboard Backend", lifespan=lifespan)

# 允许跨域（本地调试开发环境）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/sectors/history")
async def get_sectors_history():
    return {
        "code": 200,
        "data": fetcher.history_cache
    }

@app.websocket("/ws/capital-flow")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # 等待客户端发来的数据（心跳包或其他配置变更）
            data = await websocket.receive_json()
            # 这里接收前端的心跳包 {"type": "pong"}
            if data.get("type") == "pong":
                # 维持长连接连接状态
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket)

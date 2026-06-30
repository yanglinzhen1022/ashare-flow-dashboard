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

import httpx
@app.get("/api/sectors/history/{code}")
async def get_sector_history(code: str, period: str = "1"):
    try:
        # Default intraday is klt=1. Daily K-line is klt=101
        klt_val = "101" if period == "daily" else "1"
        url = fetcher.api_url.replace("/api/qt/clist/get", "/api/qt/stock/fflow/kline/get")
        params = {
            "secid": f"90.{code}",
            "klt": klt_val,
            "lmt": "30",
            "fields1": "f1,f2,f3,f7",
            "fields2": "f51,f52"
        }
        client = fetcher.get_client()
        r = await client.get(url, params=params, headers=fetcher.headers, timeout=5)
        r.raise_for_status()
        data = r.json().get("data")
        if not data:
            return {"code": 200, "data": {"timestamps": [], "values": []}}
        klines = data.get("klines", [])
        timestamps = []
        values = []
        to_yicang = 100000000.0
        for k in klines:
            parts = k.split(",")
            if len(parts) >= 2:
                t_str = parts[0].split(" ")[-1]
                val = round(float(parts[1]) / to_yicang, 2)
                timestamps.append(t_str)
                values.append(val)
        return {"code": 200, "data": {"timestamps": timestamps, "values": values}}
    except Exception as e:
        print(f"获取板块 {code} 历史走势失败: {e}")
        return {"code": 500, "message": str(e)}


import time
from app.config import Config

# 核心个股数据内存缓存，避免高频切换及定时轮询触发东财 CDN 防刷限制，缓存时效 30 秒
stocks_cache = {}

@app.get("/api/sectors/{code}/stocks")
async def get_sector_stocks(code: str):
    # 1. 检查缓存是否命中且有效
    now_ts = time.time()
    if code in stocks_cache:
        cache_ts, cached_stocks = stocks_cache[code]
        if now_ts - cache_ts < 30.0:
            return {"code": 200, "data": {"stocks": cached_stocks}}

    url = Config.EASTMONEY_API_URL
    params = {
        "pn": "1",
        "pz": "10",
        "po": "1",
        "np": "1",
        "fltt": "2",
        "invt": "2",
        "fid": "f62",
        "fs": f"b:{code}",
        "fields": "f2,f3,f12,f14,f62"
    }
    
    try:
        client = fetcher.get_client()
        r = await client.get(url, params=params, headers=fetcher.headers, timeout=5)
        r.raise_for_status()
        diff = r.json().get("data", {}).get("diff", []) or []
        stocks = []
        to_yicang = 100000000.0
        for item in diff:
            f2 = item.get("f2")
            f3 = item.get("f3")
            f12 = item.get("f12")
            f14 = item.get("f14")
            f62 = item.get("f62")
            
            def safe_float(v):
                try:
                    return float(v)
                except (TypeError, ValueError):
                    return 0.0
            
            stocks.append({
                "code": f12 or "",
                "name": f14 or "",
                "price": safe_float(f2),
                "change_pct": safe_float(f3),
                "main_net_inflow": round(safe_float(f62) / to_yicang, 2)
            })
        
        # 2. 成功获取后写入缓存
        stocks_cache[code] = (time.time(), stocks)
        return {"code": 200, "data": {"stocks": stocks}}
    except Exception as e:
        print(f"获取板块 {code} 核心个股失败: {e}")
        return {"code": 500, "message": str(e)}


@app.get("/api/stocks/search")
async def search_stock(q: str):
    try:
        # 1. Resolve stock input to QuoteID
        client = fetcher.get_client()
        suggest_url = f"https://searchapi.eastmoney.com/api/suggest/get?input={q}&type=14"
        r_suggest = await client.get(suggest_url, headers=fetcher.headers, timeout=5)
        r_suggest.raise_for_status()
        # Suggest parsing:
        quotation_table = r_suggest.json().get("QuotationCodeTable") or {}
        data_table = quotation_table.get("Data") or []
        if not data_table:
            return {"code": 404, "message": "未找到匹配个股"}
        
        target_stock = data_table[0]
        quote_id = target_stock.get("QuoteID")
        stock_code = target_stock.get("Code")
        stock_name = target_stock.get("Name")
        
        # 2. Query stock profile to get sectors f127, f129
        profile_url = f"https://push2his.eastmoney.com/api/qt/stock/get?secid={quote_id}&fields=f127,f129"
        r_profile = await client.get(profile_url, headers=fetcher.headers, timeout=5)
        r_profile.raise_for_status()
        # Profile parsing:
        profile_data = r_profile.json().get("data") or {}
        
        industry_name = profile_data.get("f127") or ""
        concept_names_str = profile_data.get("f129") or ""
        concept_names = [c.strip() for c in concept_names_str.split(",") if c.strip()]
        
        # 3. Match against current active list of sectors
        industry_match = None
        concept_matches = []
        
        # Helper to search matching code
        all_s = fetcher.latest_data.get("industry", []) + fetcher.latest_data.get("concept", [])
        for s in all_s:
            if s["name"] == industry_name:
                industry_match = {"code": s["code"], "name": s["name"]}
            elif s["name"] in concept_names:
                concept_matches.append({"code": s["code"], "name": s["name"]})
                
        return {
            "code": 200,
            "data": {
                "stock_code": stock_code,
                "stock_name": stock_name,
                "industry": industry_match,
                "concepts": concept_matches
            }
        }
    except Exception as e:
        print(f"搜索个股 {q} 失败: {e}")
        return {"code": 500, "message": str(e)}


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

# 挂载前端静态文件（生产/单进程部署环境）
import os
from fastapi.staticfiles import StaticFiles

# 确定 frontend/dist 路径
current_dir = os.path.dirname(os.path.abspath(__file__))
dist_path = os.path.abspath(os.path.join(current_dir, "..", "..", "frontend", "dist"))

if os.path.exists(dist_path):
    app.mount("/", StaticFiles(directory=dist_path, html=True), name="static")


import asyncio
import os
import time
from contextlib import asynccontextmanager
from typing import Dict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import Config
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


def _api_error(action: str, exc: Exception) -> dict:
    """东财接口统一异常兜底：记录日志并返回 500 JSON 响应"""
    print(f"{action}失败: {exc}")
    return {"code": 500, "message": str(exc)}


def _safe_float(val) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


@app.get("/api/sectors/history")
async def get_sectors_history():
    return {
        "code": 200,
        "data": fetcher.history_cache
    }


@app.get("/api/sectors/history/{code}")
async def get_sector_history(code: str, period: str = "1"):
    if period != "daily":
        data = fetcher.history_cache.get(code, {"timestamps": [], "values": []})
        return {
            "code": 200,
            "data": data
        }
    try:
        # Daily K-line is klt=101
        url = fetcher.api_url.replace("/api/qt/clist/get", "/api/qt/stock/fflow/kline/get")
        params = {
            "secid": f"90.{code}",
            "klt": "101",
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
        return _api_error(f"获取板块 {code} 历史走势", e)


# 核心个股数据内存缓存，避免高频切换及定时轮询触发东财 CDN 防刷限制，缓存时效见 Config.STOCKS_CACHE_TTL
stocks_cache: Dict[str, tuple] = {}


@app.get("/api/sectors/{code}/stocks")
async def get_sector_stocks(code: str, limit: int = 50):
    safe_limit = min(max(limit, 1), 100)
    # 1. 检查缓存是否命中且有效
    now_ts = time.time()
    if code in stocks_cache:
        cache_ts, cached_stocks = stocks_cache[code]
        if now_ts - cache_ts < Config.STOCKS_CACHE_TTL and len(cached_stocks) >= safe_limit:
            return {"code": 200, "data": {"stocks": cached_stocks[:safe_limit]}}

    url = Config.EASTMONEY_API_URL
    params = {
        "pn": "1",
        "pz": str(safe_limit),
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
        data = r.json().get("data") or {}
        diff = data.get("diff") or []
        stocks = []
        to_yicang = 100000000.0
        for item in diff:
            stocks.append({
                "code": item.get("f12") or "",
                "name": item.get("f14") or "",
                "price": _safe_float(item.get("f2")),
                "change_pct": _safe_float(item.get("f3")),
                "main_net_inflow": round(_safe_float(item.get("f62")) / to_yicang, 2)
            })

        # 2. 成功获取后写入缓存，并淘汰已过期条目防止缓存无界增长
        expired_keys = [
            k for k, (ts, _) in stocks_cache.items()
            if now_ts - ts >= Config.STOCKS_CACHE_TTL
        ]
        for k in expired_keys:
            del stocks_cache[k]
        stocks_cache[code] = (now_ts, stocks)
        return {"code": 200, "data": {"stocks": stocks}}
    except Exception as e:
        return _api_error(f"获取板块 {code} 核心个股", e)


@app.get("/api/stocks/search")
async def search_stock(q: str):
    try:
        # 1. Resolve stock input to QuoteID
        client = fetcher.get_client()
        suggest_url = "https://searchapi.eastmoney.com/api/suggest/get"
        r_suggest = await client.get(
            suggest_url,
            params={"input": q, "type": 14},
            headers=fetcher.headers,
            timeout=5
        )
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
        profile_url = "https://push2his.eastmoney.com/api/qt/stock/get"
        r_profile = await client.get(
            profile_url,
            params={"secid": quote_id, "fields": "f127,f129"},
            headers=fetcher.headers,
            timeout=5
        )
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
        return _api_error(f"搜索个股 {q}", e)


# 个股详情弹窗内存缓存: key 前缀区分类型, 值为 (写入时间戳, 数据)
# intraday 缓存 TTL 与个股列表一致; kline 为日级数据, TTL 放宽到 5 分钟
stock_detail_cache: Dict[str, tuple] = {}


def _stock_secid(code: str) -> str:
    """构造东财 secid: 6 开头为沪市 (market 1), 其余按深市 (market 0) 处理"""
    return f"1.{code}" if code.startswith("6") else f"0.{code}"


def _get_stock_detail_cache(key: str, ttl: float):
    entry = stock_detail_cache.get(key)
    if entry is None:
        return None
    ts, payload = entry
    if time.time() - ts < ttl:
        return payload
    return None


def _set_stock_detail_cache(key: str, payload: dict):
    """写入缓存并淘汰已过期条目, 防止无界增长 (与 stocks_cache 同模式)"""
    now_ts = time.time()
    expired_keys = [
        k for k, (ts, _) in stock_detail_cache.items()
        if now_ts - ts >= max(Config.STOCKS_CACHE_TTL, 300.0)
    ]
    for k in expired_keys:
        del stock_detail_cache[k]
    stock_detail_cache[key] = (now_ts, payload)


@app.get("/api/stocks/{code}/intraday")
async def get_stock_intraday(code: str):
    cache_key = f"intraday:{code}"
    cached = _get_stock_detail_cache(cache_key, Config.STOCKS_CACHE_TTL)
    if cached is not None:
        return {"code": 200, "data": cached}

    secid = _stock_secid(code)
    try:
        client = fetcher.get_client()
        # 1. 今日分时曲线 (trends2: 时间, 现价, 成交量, 成交额, 均价)
        r_trends = await client.get(
            "https://push2his.eastmoney.com/api/qt/stock/trends2/get",
            params={
                "secid": secid,
                "fields1": "f1,f2,f3,f4,f5,f6,f7,f8",
                "fields2": "f51,f53,f56,f57,f58",
                "iscr": "0",
                "ndays": "1",
                "ut": Config.EASTMONEY_UT,
            },
            headers=fetcher.headers,
            timeout=5,
        )
        r_trends.raise_for_status()
        trends_data = r_trends.json().get("data") or {}
        trends = trends_data.get("trends") or []

        timestamps = []
        prices = []
        avg_prices = []
        volumes = []
        for row in trends:
            parts = row.split(",")
            if len(parts) < 5:
                continue
            timestamps.append(parts[0].split(" ")[-1])
            prices.append(_safe_float(parts[1]))
            volumes.append(_safe_float(parts[2]))
            avg_prices.append(_safe_float(parts[4]))

        # 2. 分钟级资金流 kline (时间, 主力, 小单, 中单, 大单, 超大单; 单位: 元)
        r_fflow = await client.get(
            "https://push2.eastmoney.com/api/qt/stock/fflow/kline/get",
            params={
                "secid": secid,
                "klt": "1",
                "lmt": "300",
                "fields1": "f1,f2,f3,f7",
                "fields2": "f51,f52,f53,f54,f55,f56",
                "ut": Config.EASTMONEY_UT,
            },
            headers=fetcher.headers,
            timeout=5,
        )
        r_fflow.raise_for_status()
        fflow_klines = (r_fflow.json().get("data") or {}).get("klines") or []

        to_yicang = 100000000.0
        main_total = small_total = medium_total = large_total = super_total = 0.0
        for row in fflow_klines:
            parts = row.split(",")
            if len(parts) < 6:
                continue
            main_total += _safe_float(parts[1])
            small_total += _safe_float(parts[2])
            medium_total += _safe_float(parts[3])
            large_total += _safe_float(parts[4])
            super_total += _safe_float(parts[5])

        pre_close = _safe_float(trends_data.get("preClose"))
        last_price = prices[-1] if prices else 0.0
        change_pct = round((last_price - pre_close) / pre_close * 100, 2) if pre_close else 0.0

        payload = {
            "code": code,
            "name": trends_data.get("name") or "",
            "pre_close": pre_close,
            "last_price": last_price,
            "change_pct": change_pct,
            "timestamps": timestamps,
            "prices": prices,
            "avg_prices": avg_prices,
            "volumes": volumes,
            "main_net_inflow": round(main_total / to_yicang, 2),
            "super_large_inflow": round(super_total / to_yicang, 2),
            "large_inflow": round(large_total / to_yicang, 2),
            "medium_inflow": round(medium_total / to_yicang, 2),
            "small_inflow": round(small_total / to_yicang, 2),
        }
        _set_stock_detail_cache(cache_key, payload)
        return {"code": 200, "data": payload}
    except Exception as e:
        return _api_error(f"获取个股 {code} 分时数据", e)


@app.get("/api/stocks/{code}/kline")
async def get_stock_kline(code: str):
    cache_key = f"kline:{code}"
    cached = _get_stock_detail_cache(cache_key, 300.0)
    if cached is not None:
        return {"code": 200, "data": cached}

    secid = _stock_secid(code)
    try:
        client = fetcher.get_client()
        r = await client.get(
            "https://push2his.eastmoney.com/api/qt/stock/kline/get",
            params={
                "secid": secid,
                "klt": "101",
                "fqt": "1",
                "lmt": "120",
                "end": "20500101",
                "fields1": "f1,f2,f3,f7",
                "fields2": "f51,f52,f53,f54,f55,f56,f57",
                "ut": Config.EASTMONEY_UT,
            },
            headers=fetcher.headers,
            timeout=5,
        )
        r.raise_for_status()
        kdata = r.json().get("data") or {}
        klines = kdata.get("klines") or []

        timestamps = []
        open_arr = []
        close_arr = []
        high_arr = []
        low_arr = []
        volume_arr = []
        for row in klines:
            parts = row.split(",")
            if len(parts) < 6:
                continue
            timestamps.append(parts[0])
            open_arr.append(_safe_float(parts[1]))
            close_arr.append(_safe_float(parts[2]))
            high_arr.append(_safe_float(parts[3]))
            low_arr.append(_safe_float(parts[4]))
            volume_arr.append(_safe_float(parts[5]))

        pre_close = close_arr[-2] if len(close_arr) >= 2 else 0.0
        last_price = close_arr[-1] if close_arr else 0.0
        change_pct = round((last_price - pre_close) / pre_close * 100, 2) if pre_close else 0.0

        payload = {
            "code": code,
            "name": kdata.get("name") or "",
            "last_price": last_price,
            "change_pct": change_pct,
            "timestamps": timestamps,
            "open": open_arr,
            "close": close_arr,
            "high": high_arr,
            "low": low_arr,
            "volume": volume_arr,
        }
        _set_stock_detail_cache(cache_key, payload)
        return {"code": 200, "data": payload}
    except Exception as e:
        return _api_error(f"获取个股 {code} 日K数据", e)


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
# 确定 frontend/dist 路径
current_dir = os.path.dirname(os.path.abspath(__file__))
dist_path = os.path.abspath(os.path.join(current_dir, "..", "..", "frontend", "dist"))

if os.path.exists(dist_path):
    app.mount("/", StaticFiles(directory=dist_path, html=True), name="static")

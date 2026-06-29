import asyncio
import httpx
import time
from typing import Dict, List
from app.config import Config
from app.manager import ConnectionManager

class DataFetcher:
    def __init__(self, manager: ConnectionManager):
        self.manager = manager
        self.latest_data: Dict = {"industry": [], "concept": []}
        self.history_cache: Dict[str, Dict] = {} # 存储今日开盘以来的每分钟历史走势

    async def fetch_and_broadcast(self) -> Dict:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        async with httpx.AsyncClient() as client:
            # 1. 行业板块 f62: 主力净流入
            industry_params = {
                "pn": "1", "pz": "50", "po": "1", "np": "1",
                "fltt": "2", "invt": "2", "fid": "f62",
                "fs": "m:90 t:2", # 行业板块代码
                "fields": "f12,f14,f3,f62,f66,f72,f78,f84"
            }
            
            # 2. 概念板块 f62: 主力净流入
            concept_params = {
                "pn": "1", "pz": "50", "po": "1", "np": "1",
                "fltt": "2", "invt": "2", "fid": "f62",
                "fs": "m:90 t:3", # 概念板块代码
                "fields": "f12,f14,f3,f62,f66,f72,f78,f84"
            }
            
            formatted_industry = []
            formatted_concept = []
            
            try:
                # 并发请求行业和概念数据
                res_ind, res_con = await asyncio.gather(
                    client.get(Config.EASTMONEY_API_URL, params=industry_params, headers=headers, timeout=5),
                    client.get(Config.EASTMONEY_API_URL, params=concept_params, headers=headers, timeout=5)
                )
                
                if res_ind.status_code == 200:
                    diff = res_ind.json().get("data", {}).get("diff", [])
                    formatted_industry = self._format_items(diff)
                    
                if res_con.status_code == 200:
                    diff = res_con.json().get("data", {}).get("diff", [])
                    formatted_concept = self._format_items(diff)
                    
            except Exception as e:
                print(f"数据抓取失败: {e}")
                
            self.latest_data = {
                "timestamp": time.strftime("%H:%M:%S", time.localtime()),
                "industry": formatted_industry,
                "concept": formatted_concept
            }
            
            # 更新历史折线图缓存 (根据当前分钟记录主力资金累计额)
            current_min = time.strftime("%H:%M", time.localtime())
            self._update_history_cache(current_min, formatted_industry + formatted_concept)
            
            # 广播给全部连接客户端
            payload = {
                "type": "flow_update",
                "timestamp": self.latest_data["timestamp"],
                "data": self.latest_data
            }
            await self.manager.broadcast(payload)
            return self.latest_data

    def _format_items(self, items: List[Dict]) -> List[Dict]:
        result = []
        to_yicang = 100000000.0
        for item in items:
            result.append({
                "code": item.get("f12", ""),
                "name": item.get("f14", ""),
                "change_pct": item.get("f3", 0.0),
                "main_net_inflow": round(item.get("f62", 0.0) / to_yicang, 2),
                "super_large_inflow": round(item.get("f66", 0.0) / to_yicang, 2),
                "large_inflow": round(item.get("f72", 0.0) / to_yicang, 2),
                "medium_inflow": round(item.get("f78", 0.0) / to_yicang, 2),
                "small_inflow": round(item.get("f84", 0.0) / to_yicang, 2),
            })
        return result

    def _update_history_cache(self, current_min: str, all_sectors: List[Dict]):
        for sector in all_sectors:
            code = sector["code"]
            if code not in self.history_cache:
                self.history_cache[code] = {"timestamps": [], "values": []}
            
            # 每分钟仅记录一次最新累计主力资金流入
            timestamps = self.history_cache[code]["timestamps"]
            if not timestamps or timestamps[-1] != current_min:
                self.history_cache[code]["timestamps"].append(current_min)
                self.history_cache[code]["values"].append(sector["main_net_inflow"])
            else:
                # 如果是同一分钟内，直接更新最后一个值
                self.history_cache[code]["values"][-1] = sector["main_net_inflow"]

    async def start_loop(self):
        """启动无限循环异步调度任务，每3秒执行一次"""
        while True:
            await self.fetch_and_broadcast()
            await asyncio.sleep(Config.POLL_INTERVAL_SECONDS)

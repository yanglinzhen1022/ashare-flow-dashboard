import asyncio
from datetime import datetime, timezone, timedelta
import httpx
import time
from typing import Dict, List
from app.config import Config
from app.manager import ConnectionManager

import socket

cst_tz = timezone(timedelta(hours=8))

class DataFetcher:
    def __init__(self, manager: ConnectionManager):
        self.manager = manager
        self.latest_data: Dict = {"industry": [], "concept": []}
        self.history_cache: Dict[str, Dict] = {} # 存储今日开盘以来的每分钟历史走势
        self.last_date = datetime.now(cst_tz).strftime("%Y-%m-%d")
        self.client = None
        
        self.api_url = Config.EASTMONEY_API_URL
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Host": "push2.eastmoney.com"
        }

    async def fetch_and_broadcast(self) -> Dict:
        # 动态解析域名到 IPv4 物理地址，避免部分网络/CDN 故障下的 IPv6 强行解析导致 empty reply 或跨天失效问题
        try:
            ipv4_addr = await asyncio.to_thread(socket.gethostbyname, "push2.eastmoney.com")
            if ipv4_addr:
                self.api_url = f"http://{ipv4_addr}/api/qt/clist/get"
        except Exception as e:
            print(f"DNS 动态 IPv4 解析失败，使用之前保存的或默认 API URL: {e}")

        if self.client is None or self.client.is_closed:
            self.client = httpx.AsyncClient()
        
        # 1. 行业板块 (po=1 降序获取主力净流入前 100 名)
        industry_in_params = {
            "pn": "1", "pz": "100", "po": "1", "np": "1",
            "fltt": "2", "invt": "2", "fid": "f62",
            "fs": "m:90 t:2", # 行业板块代码
            "fields": "f6,f12,f14,f3,f62,f66,f72,f78,f84"
        }

        # 2. 行业板块 (po=0 升序获取主力净流出前 100 名)
        industry_out_params = {
            "pn": "1", "pz": "100", "po": "0", "np": "1",
            "fltt": "2", "invt": "2", "fid": "f62",
            "fs": "m:90 t:2", # 行业板块代码
            "fields": "f6,f12,f14,f3,f62,f66,f72,f78,f84"
        }
        
        # 3. 概念板块 (po=1 降序获取主力净流入前 100 名)
        concept_in_params = {
            "pn": "1", "pz": "100", "po": "1", "np": "1",
            "fltt": "2", "invt": "2", "fid": "f62",
            "fs": "m:90 t:3", # 概念板块代码
            "fields": "f6,f12,f14,f3,f62,f66,f72,f78,f84"
        }

        # 4. 概念板块 (po=0 升序获取主力净流出前 100 名)
        concept_out_params = {
            "pn": "1", "pz": "100", "po": "0", "np": "1",
            "fltt": "2", "invt": "2", "fid": "f62",
            "fs": "m:90 t:3", # 概念板块代码
            "fields": "f6,f12,f14,f3,f62,f66,f72,f78,f84"
        }
        
        formatted_industry = []
        formatted_concept = []
        
        try:
            # 并发请求行业和概念流入、流出数据（共 4 个请求）
            res_ind_in, res_ind_out, res_con_in, res_con_out = await asyncio.gather(
                self.client.get(self.api_url, params=industry_in_params, headers=self.headers, timeout=5),
                self.client.get(self.api_url, params=industry_out_params, headers=self.headers, timeout=5),
                self.client.get(self.api_url, params=concept_in_params, headers=self.headers, timeout=5),
                self.client.get(self.api_url, params=concept_out_params, headers=self.headers, timeout=5)
            )
            
            res_ind_in.raise_for_status()
            res_ind_out.raise_for_status()
            res_con_in.raise_for_status()
            res_con_out.raise_for_status()
            
            # 合并并去重行业板块
            diff_ind_in = res_ind_in.json().get("data", {}).get("diff", [])
            diff_ind_out = res_ind_out.json().get("data", {}).get("diff", [])
            
            combined_ind_dict = {}
            for item in diff_ind_in + diff_ind_out:
                code = item.get("f12")
                if code:
                    combined_ind_dict[code] = item
            
            formatted_industry = self._format_items(list(combined_ind_dict.values()))
            
            # 合并并去重概念板块
            diff_con_in = res_con_in.json().get("data", {}).get("diff", [])
            diff_con_out = res_con_out.json().get("data", {}).get("diff", [])
            
            combined_con_dict = {}
            for item in diff_con_in + diff_con_out:
                code = item.get("f12")
                if code:
                    combined_con_dict[code] = item
            
            formatted_concept = self._format_items(list(combined_con_dict.values()))
                
        except Exception as e:
            print(f"数据抓取失败: {e}")
            return self.latest_data
            
        now_cst = datetime.now(cst_tz)
        current_date = now_cst.strftime("%Y-%m-%d")
        self.latest_data = {
            "timestamp": now_cst.strftime("%H:%M:%S"),
            "industry": formatted_industry,
            "concept": formatted_concept
        }
        
        # 更新历史折线图缓存 (根据当前分钟记录主力资金累计额)
        current_min = now_cst.strftime("%H:%M")
        self._update_history_cache(current_min, formatted_industry + formatted_concept)
        
        # 广播给全部连接客户端
        payload = {
            "type": "flow_update",
            "timestamp": self.latest_data["timestamp"],
            "date": current_date,
            "data": self.latest_data
        }
        await self.manager.broadcast(payload)
        return self.latest_data

    def _safe_float(self, val) -> float:
        if val is None:
            return 0.0
        try:
            f = float(val)
            if f != f:  # Check for NaN
                return 0.0
            return f
        except (ValueError, TypeError):
            return 0.0

    def _format_items(self, items: List[Dict]) -> List[Dict]:
        result = []
        to_yicang = 100000000.0
        for item in items:
            turnover = round(self._safe_float(item.get("f6")) / to_yicang, 2)
            result.append({
                "code": item.get("f12") or "",
                "name": item.get("f14") or "",
                "change_pct": self._safe_float(item.get("f3")),
                "turnover": turnover,
                "main_net_inflow": round(self._safe_float(item.get("f62")) / to_yicang, 2),
                "super_large_inflow": round(self._safe_float(item.get("f66")) / to_yicang, 2),
                "large_inflow": round(self._safe_float(item.get("f72")) / to_yicang, 2),
                "medium_inflow": round(self._safe_float(item.get("f78")) / to_yicang, 2),
                "small_inflow": round(self._safe_float(item.get("f84")) / to_yicang, 2),
            })
        return result

    def _update_history_cache(self, current_min: str, all_sectors: List[Dict]):
        current_date = datetime.now(cst_tz).strftime("%Y-%m-%d")
        if current_date != self.last_date:
            self.history_cache.clear()
            self.last_date = current_date

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

    async def shutdown(self):
        """优雅关闭 HTTP 客户端"""
        if self.client is not None:
            await self.client.aclose()

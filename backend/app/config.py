import os

class Config:
    POLL_INTERVAL_SECONDS = 3.0
    # 核心个股内存缓存时效（秒）
    STOCKS_CACHE_TTL = 30.0
    # 东方财富大盘板块流向 API 基础 URL (使用极其稳定的 push2his 镜像域名)
    EASTMONEY_API_URL = "https://push2his.eastmoney.com/api/qt/clist/get"
    # 东财公开接口通行 token (quote 页面通用值)
    EASTMONEY_UT = "fa5fd1943c7b386f172d6893dbfba10b"

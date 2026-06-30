import os

class Config:
    POLL_INTERVAL_SECONDS = 3.0
    # 东方财富大盘板块流向 API 基础 URL (使用极其稳定的 push2his 镜像域名)
    EASTMONEY_API_URL = "https://push2his.eastmoney.com/api/qt/clist/get"

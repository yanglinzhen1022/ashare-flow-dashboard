#!/bin/bash
echo "🚀 正在启动 A股板块资金流向实时看板系统..."
echo "🔗 访问地址: http://localhost:8000"
export PYTHONPATH=backend
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000

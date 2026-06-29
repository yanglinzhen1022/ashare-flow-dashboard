# A股板块资金流向实时看板系统实现计划 (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个低延迟的 A 股行业与概念板块资金流向实时监控看板网页，支持 WebSocket 实时推送与 ECharts 可视化。

**Architecture:** 后端使用 FastAPI 启动异步后台轮询任务抓取东财板块资金 API，经过单位转换和累加后缓存在内存中；通过 WebSocket 管理器实时广播给所有在线前端客户端。前端采用 Vue 3 + TailwindCSS 进行暗黑风布局，并使用 ECharts 动态更新渲染板块热力图 (TreeMap)、主力资金走势图、流向排行榜和资金饼图。

**Tech Stack:** Python, FastAPI, httpx, uvicorn, pytest, Node.js, Vue 3, Vite, TailwindCSS, ECharts

## Global Constraints
* 后端 Python 依赖版本：`fastapi>=0.100.0`, `uvicorn>=0.22.0`, `httpx>=0.24.0`, `pytest>=7.0.0`
* 前端 Node/NPM 依赖版本：`vue>=3.3.0`, `echarts>=5.4.0`, `tailwindcss>=3.3.0`, `vite>=4.4.0`
* 视觉要求：必须为科技暗黑背景（`#0B0F19`/`#121827`），上涨/流入采用红色（`#FF4D4F`），下跌/流出采用绿色（`#22C55E`）。
* 对接数据接口更新频次：后端对东方财富 API 的主动请求频率固定为 3 秒一次，前端只接收 WebSocket 广播，不可主动高频轮询东财 API。

---

### Task 1: 后端基础结构与 WebSocket 连接管理器

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/app/manager.py`
- Create: `backend/tests/test_manager.py`

**Interfaces:**
- Consumes: None
- Produces: `ConnectionManager` 实例，提供 `connect`, `disconnect`, `broadcast` 与 `active_connections` 管理。

- [ ] **Step 1: 创建依赖文件 backend/requirements.txt**
  写入以下依赖：
  ```text
  fastapi>=0.100.0
  uvicorn>=0.22.0
  httpx>=0.24.0
  pytest>=7.0.0
  ```

- [ ] **Step 2: 编写 ConnectionManager 的测试用例**
  创建 `backend/tests/test_manager.py`：
  ```python
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
  ```

- [ ] **Step 3: 运行测试并确保其失败（未实现 ConnectionManager）**
  运行：`PYTHONPATH=backend pytest backend/tests/test_manager.py -v`
  预期：FAIL 并报 `ModuleNotFoundError: No module named 'app'`

- [ ] **Step 4: 实现 ConnectionManager 类**
  创建 `backend/app/manager.py`：
  ```python
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
          for connection in self.active_connections:
              try:
                  await connection.send_json(message)
              except Exception:
                  # 如果推送失败则忽略，实际生产中可做断连清理
                  pass
  ```

- [ ] **Step 5: 再次运行测试并确保通过**
  运行：`PYTHONPATH=backend pytest backend/tests/test_manager.py -v`
  预期：PASS

- [ ] **Step 6: 提交代码**
  ```bash
  git add backend/requirements.txt backend/app/manager.py backend/tests/test_manager.py
  git commit -m "feat(backend): add websocket connection manager and tests"
  ```

---

### Task 2: 板块资金数据获取器与调度器

**Files:**
- Create: `backend/app/config.py`
- Create: `backend/app/scheduler.py`
- Create: `backend/tests/test_scheduler.py`

**Interfaces:**
- Consumes: `ConnectionManager` 用于在拉取数据后进行广播。
- Produces: `DataFetcher` 实例，提供数据解析、内存累加缓存及 3 秒轮询调度任务。

- [ ] **Step 1: 创建配置文件 backend/app/config.py**
  ```python
  import os

  class Config:
      POLL_INTERVAL_SECONDS = 3.0
      # 东方财富大盘板块流向 API 基础 URL
      EASTMONEY_API_URL = "https://push2.eastmoney.com/api/qt/clist/get"
  ```

- [ ] **Step 2: 编写 DataFetcher 的测试用例**
  创建 `backend/tests/test_scheduler.py`：
  ```python
  import pytest
  from app.scheduler import DataFetcher
  from app.manager import ConnectionManager
  from unittest.mock import AsyncMock, patch

  @pytest.mark.asyncio
  async def test_data_fetch_and_formatting():
      mock_manager = AsyncMock(spec=ConnectionManager)
      fetcher = DataFetcher(mock_manager)
      
      # 模拟东财 API 返回格式
      mock_raw_response = {
          "data": {
              "diff": [
                  {
                      "f12": "BK0437",
                      "f14": "半导体",
                      "f3": 2.45,
                      "f62": 1235000000.0, # 12.35 亿元
                      "f66": 810000000.0,
                      "f72": 425000000.0,
                      "f78": -215000000.0,
                      "f84": -1020000000.0
                  }
              ]
          }
      }
      
      with patch("httpx.AsyncClient.get") as mock_get:
          mock_get.return_value.json = lambda: mock_raw_response
          mock_get.return_value.status_code = 200
          
          # 执行单次数据抓取与转换
          data = await fetcher.fetch_and_broadcast()
          
          assert len(data["industry"]) == 1
          item = data["industry"][0]
          assert item["code"] == "BK0437"
          assert item["name"] == "半导体"
          assert item["change_pct"] == 2.45
          assert item["main_net_inflow"] == 12.35
          assert item["super_large_inflow"] == 8.10
          assert item["large_inflow"] == 4.25
          assert item["medium_inflow"] == -2.15
          assert item["small_inflow"] == -10.20
          
          # 验证广播被触发
          mock_manager.broadcast.assert_called_once()
  ```

- [ ] **Step 3: 运行测试并确保其失败**
  运行：`PYTHONPATH=backend pytest backend/tests/test_scheduler.py -v`
  预期：FAIL 并报 `ImportError: cannot import name 'DataFetcher' from 'app.scheduler'`

- [ ] **Step 4: 实现 DataFetcher 与异步轮询逻辑**
  创建 `backend/app/scheduler.py`：
  ```python
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
  ```

- [ ] **Step 5: 再次运行测试并确保通过**
  运行：`PYTHONPATH=backend pytest backend/tests/test_scheduler.py -v`
  预期：PASS

- [ ] **Step 6: 提交代码**
  ```bash
  git add backend/app/config.py backend/app/scheduler.py backend/tests/test_scheduler.py
  git commit -m "feat(backend): implement API data fetcher, caching, and background runner"
  ```

---

### Task 3: REST API 与 WebSocket 路由集成

**Files:**
- Create: `backend/app/main.py`
- Create: `backend/tests/test_main.py`

**Interfaces:**
- Consumes: `ConnectionManager`, `DataFetcher`
- Produces: 
  * `GET /api/sectors/history`: 返回板块历史走势
  * `WS /ws/capital-flow`: 实时推送 WebSocket 端口

- [ ] **Step 1: 编写主路由和接口单元测试**
  创建 `backend/tests/test_main.py`：
  ```python
  import pytest
  from fastapi.testclient import TestClient
  from app.main import app, fetcher

  client = TestClient(app)

  def test_get_history_endpoint():
      # 预设模拟数据
      fetcher.history_cache = {
          "BK0437": {
              "timestamps": ["09:30", "09:31"],
              "values": [0.0, 1.25]
          }
      }
      
      response = client.get("/api/sectors/history")
      assert response.status_code == 200
      data = response.json()
      assert data["code"] == 200
      assert "BK0437" in data["data"]
      assert data["data"]["BK0437"]["values"] == [0.0, 1.25]

  def test_websocket_connection():
      # 测试 Websocket 心跳与通信逻辑
      with client.websocket_connect("/ws/capital-flow") as websocket:
          # 发送 pong
          websocket.send_json({"type": "pong"})
          # WebSocket 能够正常握手并没有异常关闭
  ```

- [ ] **Step 2: 运行测试并确保其失败**
  运行：`PYTHONPATH=backend pytest backend/tests/test_main.py -v`
  预期：FAIL（未定义主程序入口及路由）

- [ ] **Step 3: 实现 FastAPI 入口主路由及组件生命周期管理**
  创建 `backend/app/main.py`：
  ```python
  import asyncio
  from fastapi import FastAPI, WebSocket, WebSocketDisconnect
  from fastapi.middleware.cors import CORSMiddleware
  from app.manager import ConnectionManager
  from app.scheduler import DataFetcher

  app = FastAPI(title="A-Share Capital Flow Dashboard Backend")

  # 允许跨域（本地调试开发环境）
  app.add_middleware(
      CORSMiddleware,
      allow_origins=["*"],
      allow_credentials=True,
      allow_methods=["*"],
      allow_headers=["*"],
  )

  # 全局单例管理器
  manager = ConnectionManager()
  fetcher = DataFetcher(manager)

  @app.on_event("startup")
  async def startup_event():
      # 启动后台数据拉取轮询协程
      asyncio.create_task(fetcher.start_loop())

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
  ```

- [ ] **Step 4: 再次运行测试并确保通过**
  运行：`PYTHONPATH=backend pytest backend/tests/test_main.py -v`
  预期：PASS
  
- [ ] **Step 5: 一键运行后端全部测试以确保完整性**
  运行：`PYTHONPATH=backend pytest backend/tests/ -v`
  预期：全部 PASS

- [ ] **Step 6: 提交代码**
  ```bash
  git add backend/app/main.py backend/tests/test_main.py
  git commit -m "feat(backend): implement FastAPI endpoint router, WebSocket integration, and startup lifecycle hooks"
  ```

---

### Task 4: 前端脚手架搭建与样式系统配置

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.js`
- Create: `frontend/tailwind.config.js`
- Create: `frontend/src/assets/index.css`
- Create: `frontend/src/main.js`
- Create: `frontend/src/App.vue`

**Interfaces:**
- Consumes: Backend WebSocket & REST APIs.
- Produces: 前端核心脚手架、开发代理服务、暗黑界面布局底盘。

- [ ] **Step 1: 创建依赖管理文件 frontend/package.json**
  ```json
  {
    "name": "a-share-capital-flow-frontend",
    "version": "1.0.0",
    "scripts": {
      "dev": "vite",
      "build": "vite build",
      "preview": "vite preview"
    },
    "dependencies": {
      "echarts": "^5.4.3",
      "vue": "^3.3.4"
    },
    "devDependencies": {
      "@vitejs/plugin-vue": "^4.2.3",
      "autoprefixer": "^10.4.14",
      "postcss": "^8.4.24",
      "tailwindcss": "^3.3.2",
      "vite": "^4.4.5"
    }
  }
  ```

- [ ] **Step 2: 创建打包及服务配置文件 frontend/vite.config.js**
  配置本地代理转接开发服请求，避免跨域报错：
  ```javascript
  import { defineConfig } from 'vite'
  import vue from '@vitejs/plugin-vue'

  export default defineConfig({
    plugins: [vue()],
    server: {
      port: 5173,
      proxy: {
        '/api': {
          target: 'http://localhost:8000',
          changeOrigin: true
        },
        '/ws': {
          target: 'ws://localhost:8000',
          ws: true
        }
      }
    }
  })
  ```

- [ ] **Step 3: 创建样式配置文件 frontend/tailwind.config.js**
  ```javascript
  /** @type {import('tailwindcss').Config} */
  export default {
    content: [
      "./index.html",
      "./src/**/*.{vue,js,ts,jsx,tsx}",
    ],
    theme: {
      extend: {
        colors: {
          stockBg: '#0B0F19',
          panelBg: '#121827',
          stockRed: '#FF4D4F',
          stockGreen: '#22C55E',
        }
      },
    },
    plugins: [],
  }
  ```

- [ ] **Step 4: 创建公共全局 CSS 样式文件 frontend/src/assets/index.css**
  ```css
  @tailwind base;
  @tailwind components;
  @tailwind utilities;

  body {
    background-color: #0B0F19;
    color: #E5E7EB;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    margin: 0;
    padding: 0;
    overflow: hidden; /* 直播场景固定窗口，禁止滚动 */
  }
  ```

- [ ] **Step 5: 创建前端加载入口 frontend/src/main.js**
  ```javascript
  import { createApp } from 'vue'
  import App from './App.vue'
  import './assets/index.css'

  createApp(App).mount('#app')
  ```

- [ ] **Step 6: 创建核心页面容器骨架 frontend/src/App.vue**
  实现自适应双列布局以及后台 WebSocket 心跳维护链路：
  ```vue
  <template>
    <div class="h-screen w-screen bg-stockBg text-gray-200 flex flex-col p-4 box-border">
      <!-- 头部状态栏 -->
      <header class="flex justify-between items-center bg-panelBg rounded-lg px-6 py-3 mb-4 border border-gray-800">
        <div class="flex items-center gap-4">
          <h1 class="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-red-400 to-yellow-500">
            A股板块资金流向实时监控看板
          </h1>
          <span :class="['px-2 py-0.5 rounded text-xs', wsStatusColor]">
            {{ wsStatusText }}
          </span>
        </div>
        <div class="text-gray-400 text-sm font-mono flex items-center gap-4">
          <span>大盘实时刷新(3s/次)</span>
          <span>系统时间: {{ currentTime }}</span>
        </div>
      </header>

      <!-- 主要网格排版 -->
      <main class="flex-1 grid grid-cols-12 gap-4 overflow-hidden">
        <!-- 左半部分：TreeMap 与 走势曲线 -->
        <div class="col-span-8 flex flex-col gap-4 overflow-hidden h-full">
          <div class="flex-1 bg-panelBg rounded-lg p-4 border border-gray-800 relative min-h-[300px]">
            <h2 class="text-lg font-bold mb-2">行业/概念板块主力净流入 TreeMap</h2>
            <div id="treemap-chart" class="w-full h-full pb-8"></div>
          </div>
          <div class="h-[250px] bg-panelBg rounded-lg p-4 border border-gray-800 relative">
            <h2 class="text-lg font-bold mb-2">板块累计资金流入流出趋势 (走势曲线)</h2>
            <div id="line-chart" class="w-full h-full pb-8"></div>
          </div>
        </div>

        <!-- 右半部分：主力流入流出红绿排行 + 资金占比饼图 -->
        <div class="col-span-4 flex flex-col gap-4 overflow-hidden h-full">
          <div class="flex-1 bg-panelBg rounded-lg p-4 border border-gray-800 overflow-y-auto flex flex-col">
            <h2 class="text-lg font-bold mb-2">板块主力净流入 Top 10</h2>
            <!-- 资金流入流出双排排行 -->
            <div class="grid grid-cols-2 gap-4 flex-1 overflow-hidden">
              <div class="flex flex-col">
                <div class="text-stockRed font-bold text-center border-b border-gray-800 pb-1 mb-2">流入榜</div>
                <div class="flex-1 overflow-y-auto space-y-2" id="inflow-ranking"></div>
              </div>
              <div class="flex flex-col">
                <div class="text-stockGreen font-bold text-center border-b border-gray-800 pb-1 mb-2">流出榜</div>
                <div class="flex-1 overflow-y-auto space-y-2" id="outflow-ranking"></div>
              </div>
            </div>
          </div>
          <div class="h-[250px] bg-panelBg rounded-lg p-4 border border-gray-800 relative">
            <h2 class="text-lg font-bold mb-2">所选板块资金分布明细</h2>
            <div id="pie-chart" class="w-full h-full pb-8"></div>
          </div>
        </div>
      </main>
    </div>
  </template>

  <script setup>
  import { ref, onMounted, onUnmounted, computed } from 'vue'

  const wsStatus = ref('connecting') // connecting, connected, disconnected
  const currentTime = ref('')
  const socket = ref(null)

  const wsStatusText = computed(() => {
    if (wsStatus.value === 'connecting') return '连接中 🟡'
    if (wsStatus.value === 'connected') return '已连接 🟢'
    return '断开连接 🔴'
  })

  const wsStatusColor = computed(() => {
    if (wsStatus.value === 'connecting') return 'bg-yellow-500/20 text-yellow-400'
    if (wsStatus.value === 'connected') return 'bg-green-500/20 text-green-400'
    return 'bg-red-500/20 text-red-400'
  })

  // 维持系统时钟
  const updateTime = () => {
    const now = new Date()
    currentTime.value = now.toLocaleTimeString()
  }

  // 建立 WebSocket 连接及心跳
  let pingInterval = null
  const connectWS = () => {
    wsStatus.value = 'connecting'
    const protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://'
    const host = window.location.host
    socket.value = new WebSocket(`${protocol}${host}/ws/capital-flow`)

    socket.value.onopen = () => {
      wsStatus.value = 'connected'
      // 开启心跳
      pingInterval = setInterval(() => {
        if (socket.value.readyState === WebSocket.OPEN) {
          socket.value.send(JSON.stringify({ type: 'pong' }))
        }
      }, 10000)
    }

    socket.value.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data)
        if (payload.type === 'flow_update') {
          // 在后续任务中进行真正的图表绑定渲染
          window.handleFlowUpdate && window.handleFlowUpdate(payload.data)
        }
      } catch (err) {
        console.error('解析推送包错误:', err)
      }
    }

    socket.value.onclose = () => {
      wsStatus.value = 'disconnected'
      clearInterval(pingInterval)
      // 3秒后指数退避重连
      setTimeout(connectWS, 3000)
    }
  }

  onMounted(() => {
    connectWS()
    updateTime()
    setInterval(updateTime, 1000)
  })

  onUnmounted(() => {
    if (socket.value) socket.value.close()
    clearInterval(pingInterval)
  })
  </script>
  ```

- [ ] **Step 7: 创建静态骨架 HTML index.html (根目录)**
  ```html
  <!DOCTYPE html>
  <html lang="zh-CN">
    <head>
      <meta charset="UTF-8" />
      <link rel="icon" type="image/svg+xml" href="/vite.svg" />
      <meta name="viewport" content="width=device-width, initial-scale=1.0" />
      <title>A股板块资金流向实时监控看板</title>
    </head>
    <body class="bg-[#0B0F19]">
      <div id="app"></div>
      <script type="module" src="/src/main.js"></script>
    </body>
  </html>
  ```

- [ ] **Step 8: 提交代码**
  ```bash
  git add frontend/package.json frontend/vite.config.js frontend/tailwind.config.js frontend/src/assets/index.css frontend/src/main.js frontend/src/App.vue index.html
  git commit -m "feat(frontend): scaffold Vue3 application with TailwindCSS configure"
  ```

---

### Task 5: 核心图表可视化模块开发与 WebSocket 联动

**Files:**
- Modify: `frontend/src/App.vue`
- Create: `frontend/src/charts.js`

**Interfaces:**
- Consumes: WebSocket 广播载荷，REST `/api/sectors/history` 数据。
- Produces: 完整图表绘制渲染逻辑。

- [ ] **Step 1: 创建独立图表工具库 frontend/src/charts.js**
  集中管理 ECharts 实例的初始化及配置构建函数：
  ```javascript
  import * as echarts from 'echarts'

  export class ChartEngine {
    constructor() {
      this.treemapChart = null
      this.lineChart = null
      this.pieChart = null
      this.historyData = {}
      this.selectedSectorCode = null
    }

    initCharts() {
      const treemapDom = document.getElementById('treemap-chart')
      const lineDom = document.getElementById('line-chart')
      const pieDom = document.getElementById('pie-chart')

      if (treemapDom) this.treemapChart = echarts.init(treemapDom, 'dark')
      if (lineDom) this.lineChart = echarts.init(lineDom, 'dark')
      if (pieDom) this.pieChart = echarts.init(pieDom, 'dark')

      window.addEventListener('resize', () => {
        this.treemapChart && this.treemapChart.resize()
        this.lineChart && this.lineChart.resize()
        this.pieChart && this.pieChart.resize()
      })
    }

    async loadHistoryData() {
      try {
        const response = await fetch('/api/sectors/history')
        const result = await response.json()
        if (result.code === 200) {
          this.historyData = result.data
        }
      } catch (err) {
        console.error('加载历史累计曲线数据失败:', err)
      }
    }

    renderTreeMap(allSectors) {
      if (!this.treemapChart) return

      // TreeMap 数据节点构造
      const data = allSectors.map(s => ({
        name: `${s.name}\n${s.main_net_inflow > 0 ? '+' : ''}${s.main_net_inflow}亿\n${s.change_pct}%`,
        value: Math.abs(s.main_net_inflow), // 面积由流入或流出量绝对值代表大小
        code: s.code,
        flow: s.main_net_inflow,
        details: s
      }))

      const option = {
        backgroundColor: 'transparent',
        tooltip: {
          formatter: (info) => {
            const d = info.data.details
            if (!d) return ''
            return `
              <div class="p-2 font-mono text-sm text-white">
                <b class="text-base">${d.name}</b> (${d.code})<br/>
                今日涨跌幅: <span class="${d.change_pct >= 0 ? 'text-red-500' : 'text-green-500'}">${d.change_pct}%</span><br/>
                主力净流入: <span class="${d.main_net_inflow >= 0 ? 'text-red-500' : 'text-green-500'}">${d.main_net_inflow} 亿</span><br/>
                <hr class="border-gray-800 my-1"/>
                超大单: ${d.super_large_inflow} 亿<br/>
                大单: ${d.large_inflow} 亿<br/>
                中单: ${d.medium_inflow} 亿<br/>
                小单: ${d.small_inflow} 亿
              </div>
            `
          }
        },
        series: [{
          type: 'treemap',
          data: data,
          roam: false,
          nodeClick: 'select',
          breadcrumb: { show: false },
          label: {
            show: true,
            formatter: '{b}',
            fontSize: 12
          },
          levels: [{
            itemStyle: {
              borderWidth: 2,
              borderColor: '#121827',
              gapWidth: 1
            }
          }],
          // 颜色渐变判定：红涨绿跌
          visualMin: -10,
          visualMax: 10,
          visualDimension: 'flow',
          inRange: {
            color: ['#22C55E', '#1F2937', '#FF4D4F'] # 绿色 -> 中间暗色 -> 红色
          }
        }]
      }

      this.treemapChart.setOption(option)

      // 绑定点击事件，展示对应板块的资金结构和走势
      this.treemapChart.off('click')
      this.treemapChart.on('click', (params) => {
        if (params.data && params.data.code) {
          this.selectedSectorCode = params.data.code
          this.renderPieChart(params.data.details)
          this.renderLineChart()
        }
      })
    }

    renderLineChart() {
      if (!this.lineChart || !this.selectedSectorCode) return
      const history = this.historyData[this.selectedSectorCode]
      if (!history) return

      const option = {
        backgroundColor: 'transparent',
        grid: { top: 20, bottom: 20, left: 40, right: 20 },
        tooltip: { trigger: 'axis' },
        xAxis: {
          type: 'category',
          data: history.timestamps,
          axisLine: { lineStyle: { color: '#4B5563' } }
        },
        yAxis: {
          type: 'value',
          axisLine: { lineStyle: { color: '#4B5563' } },
          splitLine: { lineStyle: { color: '#1F2937' } }
        },
        series: [{
          type: 'line',
          data: history.values,
          smooth: true,
          showSymbol: false,
          lineStyle: { color: '#FF4D4F', width: 2 },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(255, 77, 79, 0.4)' },
              { offset: 1, color: 'rgba(255, 77, 79, 0.0)' }
            ])
          }
        }]
      }
      this.lineChart.setOption(option, true)
    }

    renderPieChart(d) {
      if (!this.pieChart || !d) return

      const option = {
        backgroundColor: 'transparent',
        tooltip: { trigger: 'item' },
        legend: { bottom: 0, textStyle: { color: '#E5E7EB' } },
        series: [{
          type: 'pie',
          radius: ['40%', '70%'],
          center: ['50%', '45%'],
          avoidLabelOverlap: false,
          label: { show: false },
          data: [
            { value: Math.abs(d.super_large_inflow), name: `超大单 (${d.super_large_inflow}亿)`, itemStyle: { color: d.super_large_inflow >= 0 ? '#EF4444' : '#10B981' } },
            { value: Math.abs(d.large_inflow), name: `大单 (${d.large_inflow}亿)`, itemStyle: { color: d.large_inflow >= 0 ? '#F87171' : '#34D399' } },
            { value: Math.abs(d.medium_inflow), name: `中单 (${d.medium_inflow}亿)`, itemStyle: { color: d.medium_inflow >= 0 ? '#FCD34D' : '#60A5FA' } },
            { value: Math.abs(d.small_inflow), name: `小单 (${d.small_inflow}亿)`, itemStyle: { color: d.small_inflow >= 0 ? '#F3F4F6' : '#9CA3AF' } }
          ]
        }]
      }
      this.pieChart.setOption(option, true)
    }

    renderRankList(allSectors) {
      // 按照资金流向由大到小排序
      const sorted = [...allSectors].sort((a, b) => b.main_net_inflow - a.main_net_inflow)
      
      const inflowDom = document.getElementById('inflow-ranking')
      const outflowDom = document.getElementById('outflow-ranking')
      if (!inflowDom || !outflowDom) return

      // 提取 Top 10 流入与 Top 10 流出
      const inflowTop = sorted.slice(0, 10)
      const outflowTop = sorted.slice(-10).reverse()

      // 绘制流入榜
      inflowDom.innerHTML = inflowTop.map((item, idx) => `
        <div class="flex justify-between items-center bg-gray-900/40 p-2 rounded border-l-4 border-stockRed font-mono text-sm">
          <span class="text-gray-400 font-bold w-4">${idx + 1}</span>
          <span class="text-gray-200 font-medium truncate w-16">${item.name}</span>
          <span class="text-stockRed font-bold">+${item.main_net_inflow.toFixed(2)}亿</span>
        </div>
      `).join('')

      // 绘制流出榜
      outflowDom.innerHTML = outflowTop.map((item, idx) => `
        <div class="flex justify-between items-center bg-gray-900/40 p-2 rounded border-l-4 border-stockGreen font-mono text-sm">
          <span class="text-gray-400 font-bold w-4">${idx + 1}</span>
          <span class="text-gray-200 font-medium truncate w-16">${item.name}</span>
          <span class="text-stockGreen font-bold">${item.main_net_inflow.toFixed(2)}亿</span>
        </div>
      `).join('')
    }
  }
  ```

- [ ] **Step 2: 在 App.vue 中引入 Charts 并驱动交互**
  编辑修改 `frontend/src/App.vue` 中的 `<script>` 区段：
  ```vue
  <script setup>
  import { ref, onMounted, onUnmounted, computed } from 'vue'
  import { ChartEngine } from './charts.js'

  const wsStatus = ref('connecting')
  const currentTime = ref('')
  const socket = ref(null)
  const engine = ref(null)

  const wsStatusText = computed(() => {
    if (wsStatus.value === 'connecting') return '连接中 🟡'
    if (wsStatus.value === 'connected') return '已连接 🟢'
    return '断开连接 🔴'
  })

  const wsStatusColor = computed(() => {
    if (wsStatus.value === 'connecting') return 'bg-yellow-500/20 text-yellow-400'
    if (wsStatus.value === 'connected') return 'bg-green-500/20 text-green-400'
    return 'bg-red-500/20 text-red-400'
  })

  const updateTime = () => {
    const now = new Date()
    currentTime.value = now.toLocaleTimeString()
  }

  // 绑定全局 WebSocket 回调，渲染最新的图表和数据
  const connectWS = () => {
    wsStatus.value = 'connecting'
    const protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://'
    const host = window.location.host
    socket.value = new WebSocket(`${protocol}${host}/ws/capital-flow`)

    socket.value.onopen = () => {
      wsStatus.value = 'connected'
      setInterval(() => {
        if (socket.value.readyState === WebSocket.OPEN) {
          socket.value.send(JSON.stringify({ type: 'pong' }))
        }
      }, 10000)
    }

    socket.value.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data)
        if (payload.type === 'flow_update') {
          const allSectors = [...payload.data.industry, ...payload.data.concept]
          
          if (engine.value) {
            // 1. 渲染热力图
            engine.value.renderTreeMap(allSectors)
            // 2. 渲染排行榜
            engine.value.renderRankList(allSectors)
            
            // 3. 更新折线走势图的缓存记录
            const currentMin = payload.data.timestamp.substring(0, 5) // "HH:MM"
            for (const s of allSectors) {
              const code = s.code
              if (!engine.value.historyData[code]) {
                engine.value.historyData[code] = { timestamps: [], values: [] }
              }
              const timestamps = engine.value.historyData[code].timestamps
              if (!timestamps || timestamps[timestamps.length - 1] !== currentMin) {
                engine.value.historyData[code].timestamps.push(currentMin)
                engine.value.historyData[code].values.push(s.main_net_inflow)
              } else {
                engine.value.historyData[code].values[timestamps.length - 1] = s.main_net_inflow
              }
            }
            
            // 4. 如果当前选中了板块，则更新其饼图与折线图
            if (engine.value.selectedSectorCode) {
              const target = allSectors.find(s => s.code === engine.value.selectedSectorCode)
              if (target) {
                engine.value.renderPieChart(target)
              }
              engine.value.renderLineChart()
            } else if (allSectors.length > 0) {
              // 默认初始加载时选中第1个板块展示结构
              engine.value.selectedSectorCode = allSectors[0].code
              engine.value.renderPieChart(allSectors[0])
              engine.value.renderLineChart()
            }
          }
        }
      } catch (err) {
        console.error('前端解析与更新逻辑异常:', err)
      }
    }

    socket.value.onclose = () => {
      wsStatus.value = 'disconnected'
      setTimeout(connectWS, 3000)
    }
  }

  onMounted(async () => {
    // 实例化图表引擎并绑定 Dom 元素
    engine.value = new ChartEngine()
    engine.value.initCharts()
    
    // 异步拉取今日历史走势数据
    await engine.value.loadHistoryData()
    
    connectWS()
    updateTime()
    setInterval(updateTime, 1000)
  })

  onUnmounted(() => {
    if (socket.value) socket.value.close()
  })
  </script>
  ```

- [ ] **Step 3: 测试并验证完整页面加载和打包流程**
  1. 打开终端启动后端服务：
     运行：`python3 backend/app/main.py` 
  2. 验证前端开发编译成功：
     运行：`cd frontend && npm install && npm run build`
  预期：前端打包成功且无语法报错，并生成 `dist/` 包。

- [ ] **Step 4: 提交代码**
  ```bash
  git add frontend/src/charts.js frontend/src/App.vue
  git commit -m "feat(frontend): implement visual dashboard layouts and charts engine integration"
  ```

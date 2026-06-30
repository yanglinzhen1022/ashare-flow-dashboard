# A-Share Capital Flow Dashboard (A股板块资金流向实时监控看板)

![Dashboard Preview](./dashboard_preview.png)

A-Share Capital Flow Dashboard 是一款面向 A 股市场的**实时资金流向监控看板**。系统基于 FastAPI + Vue 3 + ECharts 5 架构，采用科技暗黑风视觉设计，支持全市场行业/概念板块资金流的实时刷新、多周期历史趋势切换、TreeMap 交互式热力图、个股反向联动板块检索等功能，为投资者提供直观的资金流向监控座舱。

---

## 🌟 核心特性

- ⚡ **3秒高频实时刷新**：后端对东方财富 API 的主动请求频率固定为 3秒一次，保障数据高灵敏度，并通过 50ms 串行间隔设计规避 CDN WAF 并发限制。
- 🔗 **高效连接池复用**：利用 `httpx.AsyncClient` 维护持久连接，结合全局 DNS 拦截补丁（强制 `eastmoney.com` 使用 IPv4 / `AF_INET` 解析），彻底解决国内部分宽带下 IPv6 CDN 握手空回复导致的请求超时问题。
- 📊 **交互式热力图 (TreeMap)**：支持热力图的 Roam（滚轮缩放与鼠标拖拽），并且支持双击热力图任意空白区域平滑重置视角。
- ⏱️ **多周期流向切换**：看板可在「今日分时、3日、5日、10日」多个流向周期之间一键切换，今日周期实时读取 WebSocket 增量内存曲线，多日周期自动获取日 K 线历史主力资金流向数据进行曲线绘制。
- 🔍 **个股反向联动检索**：在搜索框输入任意 A 股代码（如 `000725`），系统会自动解析该股所属的行业和活跃概念，自动进行页签切换并高亮选中目标板块，联动拉取其龙头股列表和资金走势。
- 🛡️ **内存与资源安全**：前后端均严格管理连接及定时器生命周期。前端组件卸载时彻底注销 ECharts 实例并清除 WebSocket 重连定时器，后端退出时优雅关闭 HTTP 客户端，绝无死锁与内存泄露风险。
- 🧪 **100% 离线测试覆盖**：编写了 18 个高覆盖率的单元测试，支持 100% 离线 mock 运行，测试执行后自动恢复全局状态，保证开发流水线持续稳定。

---

## 🛠️ 技术栈

### 后端 (Backend)
- **Python 3.10+**
- **FastAPI** (高性能异步 Web 框架)
- **Uvicorn** (ASGI 服务器)
- **HTTPX** (支持异步和连接池复用的 HTTP 客户端)
- **Pytest** + **Pytest-Asyncio** (异步测试框架)

### 前端 (Frontend)
- **Vue 3** (Composition API, `<script setup>` 语法糖)
- **ECharts 5** (高性能图表引擎，管理 TreeMap、折线图及饼图)
- **Tailwind CSS 3** (原子化 CSS 框架)
- **Vite 4** (下一代前端构建工具)

---

## 📁 目录结构

```text
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI 路由入口、WebSocket 广播及 API 接口
│   │   ├── scheduler.py     # 异步后台调度器（CST时区、重试、WAF绕过、IPv4强制解析）
│   │   ├── manager.py       # WebSocket 连接管理器（支持主动 ping/pong 心跳）
│   │   └── config.py        # 全局静态配置文件
│   ├── tests/
│   │   ├── test_main.py     # 路由及 WebSocket 逻辑单元测试
│   │   ├── test_manager.py  # WebSocket 管理器及心跳测试
│   │   ├── test_scheduler.py# 后台数据拉取及缓存管理测试
│   │   └── test_search.py   # 个股检索及 mock 测试
│   └── requirements.txt     # 后端依赖列表
│
├── frontend/
│   ├── src/
│   │   ├── App.vue          # 前端主页面（包含面板布局、WS 通信、排行榜 transitions 动画）
│   │   ├── charts.js        # ECharts 封装类（管理 TreeMap 缩放重置、走势图及饼图渲染）
│   │   └── main.js          # Vue 入口文件
│   ├── package.json         # 前端依赖及构建脚本
│   └── tailwind.config.js   # Tailwind 主题及暗黑色彩配置
│
└── run.sh                   # 一键启动脚本
```

---

## 🚀 快速开始

### 1. 克隆项目
```bash
git clone <your-repo-url>
cd stock
```

### 2. 后端配置与运行
推荐使用虚拟环境安装后端依赖：
```bash
# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -r backend/requirements.txt
```

### 3. 前端配置与构建
进入前端目录并安装依赖，然后构建静态资源：
```bash
cd frontend
npm install
npm run build
cd ..
```
构建完成后，Vite 会在 `frontend/dist` 目录下生成静态文件，FastAPI 在启动时会自动将其挂载并进行静态托管。

### 4. 运行系统
在项目根目录下，直接执行一键启动脚本即可：
```bash
bash run.sh
```
启动成功后，在浏览器中访问：**[http://localhost:8080](http://localhost:8080)**

---

## 🧪 运行测试

系统包含了完整的测试套件，在项目根目录下执行以下命令：
```bash
PYTHONPATH=backend pytest backend/tests/ -v
```
所有测试均使用 Mock 机制，支持在无网络连接的环境下运行，保障 CI/CD 流程的稳定性。

---

## 📄 开源协议

本项目基于 [MIT License](LICENSE) 协议开源。欢迎提交 Issue 和 Pull Request 进行交流与共同建设。

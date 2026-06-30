<template>
  <div class="h-screen w-screen bg-stockBg text-gray-200 flex flex-col p-4 box-border">
    <!-- 头部状态栏 -->
    <header class="flex justify-between items-center bg-panelBg rounded-lg px-6 py-3 mb-4 border border-gray-800">
      <div class="flex items-center gap-4">
        <h1 class="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-red-400 to-yellow-500">
          A股板块资金流向实时监控看板
        </h1>
        <span :class="['px-2 py-0.5 rounded text-xs font-semibold', wsStatusColor]">
          {{ wsStatusText }}
        </span>
        <!-- 全局资金数据条 -->
        <div class="hidden md:flex items-center gap-4 bg-gray-900/40 px-3 py-1 rounded border border-gray-800 text-xs font-mono">
          <span class="text-gray-400">全市场主力净流入:</span>
          <span :class="[marketTotalFlow >= 0 ? 'text-stockRed' : 'text-stockGreen', 'font-bold']">
            {{ marketTotalFlow >= 0 ? '+' : '' }}{{ marketTotalFlow.toFixed(2) }}亿
          </span>
          <div class="w-[1px] h-3 bg-gray-800"></div>
          <span class="text-gray-400">板块多空比:</span>
          <span class="text-stockRed font-bold">{{ risingSectorsCount }}</span>
          <span class="text-gray-600">/</span>
          <span class="text-stockGreen font-bold">{{ fallingSectorsCount }}</span>
        </div>
      </div>
      <div class="text-gray-400 text-sm font-mono flex items-center gap-4">
        <span>实时刷新(3s/次)</span>
        <span>系统时间: {{ currentTime }}</span>
      </div>
    </header>

    <!-- 主要网格排版 -->
    <main class="flex-1 grid grid-cols-12 gap-4 overflow-hidden">
      <!-- 左半部分：TreeMap 与 走势曲线 -->
      <div class="col-span-8 flex flex-col gap-4 overflow-hidden h-full">
        <div class="flex-1 bg-panelBg rounded-lg p-4 border border-gray-800 relative min-h-[300px] flex flex-col">
          <div class="flex justify-between items-center mb-2">
            <h2 class="text-lg font-bold">主力净流入 TreeMap</h2>
            <div class="flex items-center gap-3">
              <!-- 搜索框 -->
              <input 
                v-model="searchQuery" 
                placeholder="搜索板块..." 
                class="bg-gray-900 border border-gray-800 rounded px-2.5 py-1 text-xs text-gray-200 focus:outline-none focus:border-stockRed w-32 md:w-40 transition-all font-mono"
              />
              <div class="flex bg-gray-900/60 p-0.5 rounded border border-gray-800">
                <button 
                  @click="switchTab('industry')" 
                  :class="['px-3 py-1 text-xs rounded font-medium transition-all', currentTab === 'industry' ? 'bg-stockRed text-white' : 'text-gray-400 hover:text-gray-200']"
                >
                  行业板块
                </button>
                <button 
                  @click="switchTab('concept')" 
                  :class="['px-3 py-1 text-xs rounded font-medium transition-all', currentTab === 'concept' ? 'bg-stockRed text-white' : 'text-gray-400 hover:text-gray-200']"
                >
                  概念板块
                </button>
              </div>
            </div>
          </div>
          <div id="treemap-chart" class="flex-1 w-full"></div>
          <!-- 面积与颜色图例条 -->
          <div class="flex justify-between items-center text-[10px] text-gray-500 mt-2 px-1 font-mono border-t border-gray-800/40 pt-2 select-none">
            <span>方块大小: 主力资金买卖博弈强度 (绝对值)</span>
            <div class="flex items-center gap-2">
              <span>● 流出偏高 (≤ -15%)</span>
              <div class="w-24 h-1.5 rounded bg-gradient-to-r from-stockGreen via-gray-800 to-stockRed"></div>
              <span>流入偏高 (≥ +15%) ●</span>
            </div>
          </div>
        </div>
        <div class="h-[250px] bg-panelBg rounded-lg p-4 border border-gray-800 relative">
          <h2 class="text-lg font-bold mb-2">板块累计资金流入流出趋势 (走势曲线)</h2>
          <div id="line-chart" style="width: 100%; height: calc(100% - 40px);"></div>
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
              <TransitionGroup
                tag="div"
                name="list"
                class="flex-1 overflow-y-auto space-y-2 relative"
              >
                <div
                  v-for="(item, idx) in inflowRanking"
                  :key="item.code"
                  @click="selectSector(item)"
                  :class="['flex justify-between items-center p-2 rounded border-l-4 font-mono text-sm cursor-pointer transition-all duration-300', engine?.selectedSectorCode === item.code ? 'bg-stockRed/25 border-stockRed font-semibold scale-[1.02] border-t border-b border-r border-red-500/20' : 'bg-gray-900/40 border-stockRed hover:bg-gray-900/80']"
                >
                  <span class="text-gray-400 font-bold w-4">{{ idx + 1 }}</span>
                  <span class="text-gray-200 font-medium truncate w-16">{{ item.name }}</span>
                  <span class="text-stockRed font-bold">+{{ item.main_net_inflow.toFixed(2) }}亿</span>
                </div>
              </TransitionGroup>
            </div>
            <div class="flex flex-col">
              <div class="text-stockGreen font-bold text-center border-b border-gray-800 pb-1 mb-2">流出榜</div>
              <TransitionGroup
                tag="div"
                name="list"
                class="flex-1 overflow-y-auto space-y-2 relative"
              >
                <div
                  v-for="(item, idx) in outflowRanking"
                  :key="item.code"
                  @click="selectSector(item)"
                  :class="['flex justify-between items-center p-2 rounded border-l-4 font-mono text-sm cursor-pointer transition-all duration-300', engine?.selectedSectorCode === item.code ? 'bg-stockGreen/25 border-stockGreen font-semibold scale-[1.02] border-t border-b border-r border-green-500/20' : 'bg-gray-900/40 border-stockGreen hover:bg-gray-900/80']"
                >
                  <span class="text-gray-400 font-bold w-4">{{ idx + 1 }}</span>
                  <span class="text-gray-200 font-medium truncate w-16">{{ item.name }}</span>
                  <span class="text-stockGreen font-bold">{{ item.main_net_inflow.toFixed(2) }}亿</span>
                </div>
              </TransitionGroup>
            </div>
          </div>
        </div>
        <div class="h-[250px] bg-panelBg rounded-lg p-4 border border-gray-800 relative">
          <h2 class="text-lg font-bold mb-2">所选板块资金分布明细</h2>
          <div id="pie-chart" style="width: 100%; height: calc(100% - 40px);"></div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { ChartEngine } from './charts.js'

const wsStatus = ref('connecting') // connecting, connected, disconnected
const currentTime = ref('')
const socket = ref(null)
const engine = ref(null)
const inflowRanking = ref([])
const outflowRanking = ref([])
const lastReceivedDate = ref('')
const currentTab = ref('industry') // 'industry' or 'concept'
const latestPayload = ref(null)

// 优化交互新增的响应式属性
const searchQuery = ref('')
const marketTotalFlow = ref(0.0)
const risingSectorsCount = ref(0)
const fallingSectorsCount = ref(0)

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

// 监听搜索词变化，即时重新渲染看板
watch(searchQuery, () => {
  if (latestPayload.value && engine.value) {
    updateDashboard(latestPayload.value)
  }
})

// 切换行业/概念板块 Tab
const switchTab = (tab) => {
  currentTab.value = tab
  searchQuery.value = '' // 切换 Tab 时重置搜索词
  if (latestPayload.value && engine.value) {
    // 强制清除旧的选中状态，让 updateDashboard 自动加载新 Tab 的第一个板块作为默认
    engine.value.selectedSectorCode = null
    updateDashboard(latestPayload.value)
  }
}

// 选中某个板块进行高亮渲染
const selectSector = async (item) => {
  if (engine.value && item) {
    engine.value.selectedSectorCode = item.code
    engine.value.renderPieChart(item)
    await engine.value.fetchHistoryForSector(item.code)
    engine.value.renderLineChart()
  }
}

const updateDashboard = async (payload) => {
  if (payload.date && payload.date !== lastReceivedDate.value) {
    engine.value.historyData = {}
    lastReceivedDate.value = payload.date
  }

  const blacklist = [
    "融资融券", "深股通", "沪股通", "富时", "MSCI", "标普", "证金持股", "汇金持股", 
    "中证", "沪深", "上证", "创业板", "新三板", "国企改革", "央企改革", "标准普尔", 
    "风格", "AH股", "指数", "50_", "HS300", "深成", "深证", "周期股", "概念股", 
    "大盘", "小盘", "绩优", "百元股", "破净", "亏损", "预盈", "预增", "预减", 
    "送转", "壳资源", "独角兽", "次新", "红筹", "权重", "蓝筹", "活跃股", "ST股"
  ]
  const conceptFiltered = payload.data.concept.filter(s => {
    if (blacklist.some(k => s.name.includes(k))) return false
    // 匹配常见的指数数字（如 50, 100, 180, 300, 500, 800, 1000），排除指数板块，但保留 5G、6G 等科技题材
    if (/(?:300|500|1000|180|50|100|800)/.test(s.name) && !/(?:5G|6G)/i.test(s.name)) return false
    return true
  })
  const activeSectors = currentTab.value === 'industry' ? payload.data.industry : conceptFiltered
  const allSectors = [...payload.data.industry, ...conceptFiltered]

  // 1. 计算大盘主力总净流入与多空板块比例
  let totalFlow = 0.0
  let positiveCount = 0
  let negativeCount = 0
  for (const s of activeSectors) {
    totalFlow += s.main_net_inflow
    if (s.main_net_inflow > 0) positiveCount++
    else if (s.main_net_inflow < 0) negativeCount++
  }
  marketTotalFlow.value = totalFlow
  risingSectorsCount.value = positiveCount
  fallingSectorsCount.value = negativeCount

  // 2. 根据搜索词过滤板块
  const query = searchQuery.value.trim()
  const displaySectors = query 
    ? activeSectors.filter(s => s.name.includes(query))
    : activeSectors

  // 3. 渲染热力图
  engine.value.renderTreeMap(displaySectors)

  // 4. 更新排行榜 (依然使用原始 top 10 便于直观把握全局最强流入流出)
  inflowRanking.value = activeSectors
    .filter(s => s.main_net_inflow > 0)
    .sort((a, b) => b.main_net_inflow - a.main_net_inflow)
    .slice(0, 10)

  outflowRanking.value = activeSectors
    .filter(s => s.main_net_inflow < 0)
    .sort((a, b) => a.main_net_inflow - b.main_net_inflow)
    .slice(0, 10)

  // 5. 更新折线走势图的缓存记录
  const currentMin = payload.data.timestamp.substring(0, 5) // "HH:MM"
  for (const s of allSectors) {
    const code = s.code
    if (!engine.value.historyData[code]) {
      engine.value.historyData[code] = { timestamps: [], values: [] }
    }
    const timestamps = engine.value.historyData[code].timestamps
    if (!timestamps || timestamps.length === 0) {
      engine.value.historyData[code].timestamps = [currentMin]
      engine.value.historyData[code].values = [s.main_net_inflow]
    } else if (timestamps[timestamps.length - 1] !== currentMin) {
      engine.value.historyData[code].timestamps.push(currentMin)
      engine.value.historyData[code].values.push(s.main_net_inflow)
    } else {
      engine.value.historyData[code].values[timestamps.length - 1] = s.main_net_inflow
    }
  }

  // 6. 板块图表加载逻辑 (如果有选中板块则渲染其最新状态，否则默认选中第一个)
  if (!engine.value.selectedSectorCode && displaySectors.length > 0) {
    const defaultCode = displaySectors[0].code
    engine.value.selectedSectorCode = defaultCode
    engine.value.renderPieChart(displaySectors[0])
    await engine.value.fetchHistoryForSector(defaultCode)
    engine.value.renderLineChart()
  } else if (engine.value.selectedSectorCode) {
    const target = allSectors.find(s => s.code === engine.value.selectedSectorCode)
    if (target) {
      engine.value.renderPieChart(target)
    }
    engine.value.renderLineChart()
  }
}

// 维持系统时钟
const updateTime = () => {
  const now = new Date()
  currentTime.value = now.toLocaleTimeString()
}

// 建立 WebSocket 连接及心跳
let pingInterval = null
let reconnectTimeout = null
let isUnmounted = false

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
      if (payload.type === 'flow_update' && engine.value && !isUnmounted) {
        latestPayload.value = payload
        updateDashboard(payload)
      }
    } catch (err) {
      console.error('解析推送包错误:', err)
    }
  }

  socket.value.onclose = () => {
    wsStatus.value = 'disconnected'
    clearInterval(pingInterval)
    // 3秒后指数退避重连
    if (!isUnmounted) {
      reconnectTimeout = setTimeout(connectWS, 3000)
    }
  }
}

let clockInterval = null

onMounted(() => {
  // 实例化图表引擎并绑定 Dom 元素
  engine.value = new ChartEngine()
  engine.value.initCharts()

  connectWS()
  updateTime()
  clockInterval = setInterval(updateTime, 1000)
})

onUnmounted(() => {
  isUnmounted = true
  if (reconnectTimeout) {
    clearTimeout(reconnectTimeout)
  }
  if (clockInterval) {
    clearInterval(clockInterval)
  }
  if (pingInterval) {
    clearInterval(pingInterval)
  }
  if (socket.value) {
    socket.value.onclose = null
    socket.value.close()
  }
  if (engine.value) {
    engine.value.destroy()
    engine.value = null
  }
})
</script>

<style scoped>
.list-move {
  transition: transform 0.5s ease;
}
.list-enter-active,
.list-leave-active {
  transition: all 0.5s ease;
}
.list-enter-from,
.list-leave-to {
  opacity: 0;
  transform: translateY(10px);
}
</style>

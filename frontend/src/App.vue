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
import { ChartEngine } from './charts.js'

const wsStatus = ref('connecting') // connecting, connected, disconnected
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
        const allSectors = [...payload.data.industry, ...payload.data.concept]
        
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

onMounted(async () => {
  // 实例化图表引擎并绑定 Dom 元素
  engine.value = new ChartEngine()
  engine.value.initCharts()
  
  // 异步拉取今日历史走势数据
  await engine.value.loadHistoryData()

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

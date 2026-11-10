import * as echarts from 'echarts'

export class ChartEngine {
  constructor() {
    this.treemapChart = null
    this.lineChart = null
    this.pieChart = null
    this.modalChart = null
    this.historyData = {}
    this.selectedSectorCode = null
    this.resizeHandler = null
    this.currentPeriod = '1d'
  }

  initCharts() {
    const treemapDom = document.getElementById('treemap-chart')
    const lineDom = document.getElementById('line-chart')
    const pieDom = document.getElementById('pie-chart')

    if (treemapDom) this.treemapChart = echarts.init(treemapDom, 'dark')
    if (lineDom) this.lineChart = echarts.init(lineDom, 'dark')
    if (pieDom) this.pieChart = echarts.init(pieDom, 'dark')

    this.resizeHandler = () => {
      this.treemapChart && this.treemapChart.resize()
      this.lineChart && this.lineChart.resize()
      this.pieChart && this.pieChart.resize()
      // 弹窗实例: display:none 的页签 (offsetParent 为 null) 不 resize,
      // 切换页签时 prepareModalChart 的渲染前同步会补上
      for (const chart of [this.modalChart, this.modalKlineChart]) {
        if (chart && chart.getDom().offsetParent !== null) chart.resize()
      }
    }
    window.addEventListener('resize', this.resizeHandler)
  }

  async fetchHistoryForSector(code, period = "1d") {
    try {
      const response = await fetch(`/api/sectors/history/${code}?period=${period === "daily" ? "daily" : "1"}`)
      if (!response.ok) throw new Error(`HTTP status: ${response.status}`)
      const resData = await response.json()
      if (resData && resData.data && resData.data.timestamps && resData.data.values) {
        this.historyData[code] = {
          timestamps: resData.data.timestamps,
          values: resData.data.values
        }
      }
    } catch (e) {
      console.error(`加载板块 ${code} 历史走势异常:`, e)
      if (!this.historyData[code]) {
        this.historyData[code] = { timestamps: [], values: [] }
      }
    }
  }

  renderTreeMap(allSectors) {
    if (!this.treemapChart) return

    // TreeMap 数据节点构造
    const data = allSectors.map(s => {
      const flowVal = this.currentPeriod === '3d' ? (s.main_net_inflow_3d || 0.0) :
                     this.currentPeriod === '5d' ? (s.main_net_inflow_5d || 0.0) :
                     this.currentPeriod === '10d' ? (s.main_net_inflow_10d || 0.0) :
                     (s.main_net_inflow || 0.0)
      const periodDays = this.currentPeriod === '3d' ? 3 :
                         this.currentPeriod === '5d' ? 5 :
                         this.currentPeriod === '10d' ? 10 : 1
      const ratio = s.turnover > 0 ? (flowVal / (s.turnover * periodDays)) * 100 : 0
      return {
        name: `${s.name}\n${flowVal > 0 ? '+' : ''}${flowVal.toFixed(2)}亿\n${s.change_pct}%`,
        value: [Math.abs(flowVal), ratio],
        code: s.code,
        flow: flowVal,
        details: s
      }
    })

    const option = {
      backgroundColor: 'transparent',
      tooltip: {
        formatter: (info) => {
          const d = info.data?.details
          if (!d) return ''
          const flowVal = this.currentPeriod === '3d' ? (d.main_net_inflow_3d || 0.0) :
                         this.currentPeriod === '5d' ? (d.main_net_inflow_5d || 0.0) :
                         this.currentPeriod === '10d' ? (d.main_net_inflow_10d || 0.0) :
                         (d.main_net_inflow || 0.0)
          const periodDays = this.currentPeriod === '3d' ? 3 :
                             this.currentPeriod === '5d' ? 5 :
                             this.currentPeriod === '10d' ? 10 : 1
          const ratio = d.turnover > 0 ? (flowVal / (d.turnover * periodDays)) * 100 : 0
          const labelText = this.currentPeriod === '3d' ? '3日主力净流入' :
                            this.currentPeriod === '5d' ? '5日主力净流入' :
                            this.currentPeriod === '10d' ? '10日主力净流入' :
                            '今日主力净流入'
          return `
            <div class="p-2 font-mono text-sm text-white">
              <b class="text-base">${d.name}</b> (${d.code})<br/>
              今日涨跌幅: <span style="color: ${d.change_pct >= 0 ? '#FF4D4F' : '#22C55E'};">${d.change_pct}%</span><br/>
              ${labelText}: <span style="color: ${flowVal >= 0 ? '#FF4D4F' : '#22C55E'};">${flowVal.toFixed(2)} 亿</span><br/>
              主力净流入占比: <span style="color: ${ratio >= 0 ? '#FF4D4F' : '#22C55E'};">${ratio.toFixed(2)}%</span><br/>
              成交额: <span>${d.turnover.toFixed(2)} 亿</span><br/>
              <hr class="border-gray-800 my-1"/>
              超大单: ${d.super_large_inflow} 亿<br/>
              大单: ${d.large_inflow} 亿<br/>
              中单: ${d.medium_inflow} 亿<br/>
              小单: ${d.small_inflow} 亿
            </div>
          `
        }
      },
      visualMap: {
        show: false,
        min: -15,
        max: 15,
        dimension: 1,
        inRange: {
          color: ['#22C55E', '#1F2937', '#FF4D4F']
        }
      },
      series: [{
        type: 'treemap',
        data: data,
        roam: true,
        nodeClick: 'select',
        breadcrumb: { show: false },
        visualMin: -15,
        visualMax: 15,
        visualDimension: 1,
        label: {
          show: true,
          formatter: '{b}',
          fontSize: 12
        },
        levels: [{
          itemStyle: {
            colorMappingBy: 'value',
            borderWidth: 2,
            borderColor: '#121827',
            gapWidth: 1
          }
        }]
      }]
    }

    this.treemapChart.setOption(option)

    // 绑定双击重置
    this.treemapChart.off('dblclick')
    this.treemapChart.on('dblclick', () => {
      this.treemapChart.dispatchAction({
        type: 'treemapZoomToNode',
        targetNodeId: ''
      })
    })

    // 绑定点击事件，展示对应板块的资金结构和走势
    this.treemapChart.off('click')
    this.treemapChart.on('click', async (params) => {
      if (params.data && params.data.code) {
        this.selectedSectorCode = params.data.code
        this.renderPieChart(params.data.details)
        const periodParam = this.currentPeriod !== '1d' ? 'daily' : '1d'
        await this.fetchHistoryForSector(params.data.code, periodParam)
        this.renderLineChart()
        if (typeof this.onSectorSelect === 'function') {
          this.onSectorSelect(params.data.code, params.data.details?.name || params.data.name)
        }
      }
    })
  }

  renderLineChart() {
    if (!this.lineChart || !this.selectedSectorCode) return
    const history = this.historyData[this.selectedSectorCode]
    if (!history) return

    const lastVal = history.values[history.values.length - 1] || 0.0
    const isPositive = lastVal >= 0
    const lineColor = isPositive ? '#FF4D4F' : '#22C55E'
    const areaColorStart = isPositive ? 'rgba(255, 77, 79, 0.4)' : 'rgba(34, 197, 94, 0.4)'
    const areaColorEnd = isPositive ? 'rgba(255, 77, 79, 0.0)' : 'rgba(34, 197, 94, 0.0)'

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
        showSymbol: true,
        lineStyle: { color: lineColor, width: 2 },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: areaColorStart },
            { offset: 1, color: areaColorEnd }
          ])
        }
      }]
    }
    // 实验: notMerge=true 在与 window resize 竞争时触发 ECharts pipeline 空引用, 改为增量合并
    this.lineChart.setOption(option)
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
          { value: Math.abs(d.super_large_inflow), name: `超大单 (${d.super_large_inflow}亿)`, itemStyle: { color: d.super_large_inflow >= 0 ? '#FF4D4F' : '#22C55E' } },
          { value: Math.abs(d.large_inflow), name: `大单 (${d.large_inflow}亿)`, itemStyle: { color: d.large_inflow >= 0 ? '#FF7875' : '#52C41A' } },
          { value: Math.abs(d.medium_inflow), name: `中单 (${d.medium_inflow}亿)`, itemStyle: { color: d.medium_inflow >= 0 ? '#FFA39E' : '#73D13D' } },
          { value: Math.abs(d.small_inflow), name: `小单 (${d.small_inflow}亿)`, itemStyle: { color: d.small_inflow >= 0 ? '#FFCCC7' : '#B7EB8F' } }
        ]
      }]
    }
    this.pieChart.setOption(option, true)
  }

  // 弹窗分时/日K使用两个独立的 ECharts 实例:
  // echarts 5.6 在同一实例上跨结构切换组件数量 (分时单grid↔日K双grid) 时,
  // pipeline 按 uid 复用 series task, 可能引用尚未初始化 coordinateSystem
  // 的 model (dataSample processor 读 .type 崩溃), 且崩溃会中断 resize 重排,
  // 造成布局停留在旧尺寸。两个实例各自结构固定, 从源头消除该竞态。
  // 各实例仅增量 setOption (数据数组整体替换), 无需 replaceMerge。
  prepareModalChart(tab) {
    const id = tab === 'kline' ? 'stock-modal-kline-chart' : 'stock-modal-chart'
    const key = tab === 'kline' ? 'modalKlineChart' : 'modalChart'
    let inst = this[key]
    if (!inst) {
      const dom = document.getElementById(id)
      if (!dom) return null
      inst = echarts.init(dom, 'dark')
      this[key] = inst
    }
    // 渲染前同步实例尺寸到容器真实尺寸: 页签切换会改变容器高度
    // (分时有指标卡/日K无说明行), 保证 setOption 一次布局到位。
    // 容差 1px 避免亚像素 (如 718.5 vs 718) 触发无意义的 resize。
    // 注意: 弹窗实例不挂 ResizeObserver —— RO 对隐藏 div (display:none, 0x0)
    // 的回调会在带 series 的实例上触发完整 update 重跑, echarts 5.6 的
    // pipeline stub 竞态此时会崩溃 (dataSample 读未挂载的 coordinateSystem);
    // 窗口缩放由 window resize handler 统一处理 (隐藏实例跳过)
    const rect = inst.getDom().getBoundingClientRect()
    if (
      Math.abs(rect.width - inst.getWidth()) > 1 ||
      Math.abs(rect.height - inst.getHeight()) > 1
    ) {
      inst.resize()
    }
    return inst
  }

  disposeModalChart() {
    if (this.modalChart) {
      this.modalChart.dispose()
      this.modalChart = null
    }
    if (this.modalKlineChart) {
      this.modalKlineChart.dispose()
      this.modalKlineChart = null
    }
  }

  // 个股详情弹窗: 今日分时 (现价 + 均价)
  renderStockIntraday(d) {
    if (!this.modalChart || !d) return
    const up = (d.change_pct || 0) >= 0
    const lineColor = up ? '#FF4D4F' : '#22C55E'
    const areaColorStart = up ? 'rgba(255, 77, 79, 0.35)' : 'rgba(34, 197, 94, 0.35)'
    const areaColorEnd = up ? 'rgba(255, 77, 79, 0.0)' : 'rgba(34, 197, 94, 0.0)'

    // 右轴涨跌幅: 以昨收为基准, 与左轴价格范围对称 (昨收居中), 两轴各分4格, 网格线对齐
    const pre = d.pre_close || 0
    const all = [...(d.prices || []), ...(d.avg_prices || [])].filter(v => v > 0)
    let dev = 0
    if (pre > 0 && all.length) {
      dev = Math.max(Math.max(...all) - pre, pre - Math.min(...all)) * 1.02
    }
    const hasRightAxis = pre > 0 && dev > 0
    let yAxis
    if (hasRightAxis) {
      const pct = (v) => (v / pre) * 100
      yAxis = [
        {
          type: 'value',
          min: pre - dev,
          max: pre + dev,
          splitNumber: 4,
          axisLine: { lineStyle: { color: '#4B5563' } },
          splitLine: { lineStyle: { color: '#1F2937' } }
        },
        {
          type: 'value',
          min: pct(-dev),
          max: pct(dev),
          splitNumber: 4,
          position: 'right',
          axisLine: { show: false },
          splitLine: { show: false },
          axisLabel: { formatter: (v) => (v > 0 ? '+' : '') + v.toFixed(2) + '%' }
        }
      ]
    } else {
      yAxis = {
        type: 'value',
        scale: true,
        axisLine: { lineStyle: { color: '#4B5563' } },
        splitLine: { lineStyle: { color: '#1F2937' } }
      }
    }

    const option = {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        formatter: (params) => {
          const t = params[0].axisValue
          let html = t
          for (const p of params) {
            const v = p.value
            const pct = pre > 0 && v != null ? ((v - pre) / pre * 100).toFixed(2) : null
            html += `<br/>${p.marker}${p.seriesName}: ${v != null ? v.toFixed(2) : '-'}${pct != null ? ' (' + (pct > 0 ? '+' : '') + pct + '%)' : ''}`
          }
          return html
        }
      },
      grid: { top: 10, bottom: 24, left: 55, right: hasRightAxis ? 52 : 20 },
      xAxis: {
        type: 'category',
        data: d.timestamps,
        axisLine: { lineStyle: { color: '#4B5563' } }
      },
      yAxis,
      series: [
        {
          name: '现价',
          type: 'line',
          data: d.prices,
          smooth: true,
          showSymbol: false,
          lineStyle: { color: lineColor, width: 2 },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: areaColorStart },
              { offset: 1, color: areaColorEnd }
            ])
          },
          // 昨收基准线 (即右轴 0%)
          markLine: hasRightAxis ? {
            symbol: 'none',
            silent: true,
            label: { show: false },
            lineStyle: { color: '#6B7280', type: 'dashed', width: 1 },
            data: [{ yAxis: pre }]
          } : undefined
        },
        {
          name: '均价',
          type: 'line',
          data: d.avg_prices,
          smooth: true,
          showSymbol: false,
          lineStyle: { color: '#FBBF24', width: 1, type: 'dashed' }
        }
      ]
    }
    this.modalChart.setOption(option)
  }

  // 个股详情弹窗: 120日K线 (蜡烛图 + 成交量)
  renderStockKline(d) {
    if (!this.modalKlineChart || !d) return
    const option = {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' }
      },
      grid: [
        { top: 10, bottom: 110, left: 55, right: 20 },
        { top: '75%', bottom: 24, left: 55, right: 20 }
      ],
      xAxis: [
        {
          type: 'category',
          data: d.timestamps,
          gridIndex: 0,
          axisLine: { lineStyle: { color: '#4B5563' } },
          axisLabel: { show: false }
        },
        {
          type: 'category',
          data: d.timestamps,
          gridIndex: 1,
          axisLine: { lineStyle: { color: '#4B5563' } }
        }
      ],
      yAxis: [
        {
          type: 'value',
          scale: true,
          gridIndex: 0,
          splitLine: { lineStyle: { color: '#1F2937' } }
        },
        {
          type: 'value',
          gridIndex: 1,
          splitLine: { show: false },
          axisLabel: { show: false }
        }
      ],
      dataZoom: [{ type: 'inside', xAxisIndex: [0, 1], start: 65, end: 100 }],
      series: [
        {
          name: '日K',
          type: 'candlestick',
          data: d.timestamps.map((_, i) => [d.open[i], d.close[i], d.low[i], d.high[i]]),
          itemStyle: {
            color: '#FF4D4F',
            color0: '#22C55E',
            borderColor: '#FF4D4F',
            borderColor0: '#22C55E'
          }
        },
        {
          name: '成交量',
          type: 'bar',
          xAxisIndex: 1,
          yAxisIndex: 1,
          data: d.close.map((c, i) => ({
            value: d.volume[i],
            itemStyle: { color: c >= d.open[i] ? 'rgba(255,77,79,0.7)' : 'rgba(34,197,94,0.7)' }
          }))
        }
      ]
    }
    this.modalKlineChart.setOption(option)
  }



  destroy() {
    if (this.resizeHandler) {
      window.removeEventListener('resize', this.resizeHandler)
      this.resizeHandler = null
    }
    if (this.treemapChart) {
      this.treemapChart.dispose()
      this.treemapChart = null
    }
    if (this.lineChart) {
      this.lineChart.dispose()
      this.lineChart = null
    }
    if (this.pieChart) {
      this.pieChart.dispose()
      this.pieChart = null
    }
    this.disposeModalChart()
  }
}

import * as echarts from 'echarts'

export class ChartEngine {
  constructor() {
    this.treemapChart = null
    this.lineChart = null
    this.pieChart = null
    this.historyData = {}
    this.selectedSectorCode = null
    this.resizeHandler = null
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
    }
    window.addEventListener('resize', this.resizeHandler)
  }

  async fetchHistoryForSector(code) {
    try {
      const response = await fetch(`/api/sectors/history/${code}`)
      const result = await response.json()
      if (result.code === 200) {
        this.historyData[code] = result.data
      }
    } catch (err) {
      console.error(`加载板块 ${code} 走势失败:`, err)
    }
  }

  renderTreeMap(allSectors) {
    if (!this.treemapChart) return

    // TreeMap 数据节点构造
    const data = allSectors.map(s => {
      const ratio = s.turnover > 0 ? (s.main_net_inflow / s.turnover) * 100 : 0
      return {
        name: `${s.name}\n${s.main_net_inflow > 0 ? '+' : ''}${s.main_net_inflow}亿\n${s.change_pct}%`,
        value: [Math.abs(s.main_net_inflow), ratio],
        code: s.code,
        flow: s.main_net_inflow,
        details: s
      }
    })

    const option = {
      backgroundColor: 'transparent',
      tooltip: {
        formatter: (info) => {
          const d = info.data?.details
          if (!d) return ''
          const ratio = d.turnover > 0 ? (d.main_net_inflow / d.turnover) * 100 : 0
          return `
            <div class="p-2 font-mono text-sm text-white">
              <b class="text-base">${d.name}</b> (${d.code})<br/>
              今日涨跌幅: <span style="color: ${d.change_pct >= 0 ? '#FF4D4F' : '#22C55E'};">${d.change_pct}%</span><br/>
              主力净流入: <span style="color: ${d.main_net_inflow >= 0 ? '#FF4D4F' : '#22C55E'};">${d.main_net_inflow} 亿</span><br/>
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
        roam: false,
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

    // 绑定点击事件，展示对应板块的资金结构和走势
    this.treemapChart.off('click')
    this.treemapChart.on('click', async (params) => {
      if (params.data && params.data.code) {
        this.selectedSectorCode = params.data.code
        this.renderPieChart(params.data.details)
        await this.fetchHistoryForSector(params.data.code)
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
          { value: Math.abs(d.super_large_inflow), name: `超大单 (${d.super_large_inflow}亿)`, itemStyle: { color: d.super_large_inflow >= 0 ? '#FF4D4F' : '#22C55E' } },
          { value: Math.abs(d.large_inflow), name: `大单 (${d.large_inflow}亿)`, itemStyle: { color: d.large_inflow >= 0 ? '#FF7875' : '#52C41A' } },
          { value: Math.abs(d.medium_inflow), name: `中单 (${d.medium_inflow}亿)`, itemStyle: { color: d.medium_inflow >= 0 ? '#FFA39E' : '#73D13D' } },
          { value: Math.abs(d.small_inflow), name: `小单 (${d.small_inflow}亿)`, itemStyle: { color: d.small_inflow >= 0 ? '#FFCCC7' : '#B7EB8F' } }
        ]
      }]
    }
    this.pieChart.setOption(option, true)
  }

  async fetchHistoryForSector(code) {
    try {
      const response = await fetch(`/api/sectors/history/${code}`)
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
  }
}

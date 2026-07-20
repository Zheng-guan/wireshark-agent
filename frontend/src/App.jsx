import React, { useState, useCallback, useRef, useEffect } from 'react'
import { api } from './api.js'
import Toolbar from './components/Toolbar.jsx'
import PacketTable from './components/PacketTable.jsx'
import PacketDetail from './components/PacketDetail.jsx'
import ChatPanel from './components/ChatPanel.jsx'
import Splitter from './components/Splitter.jsx'
import SummaryPanel from './components/SummaryPanel.jsx'
import StatsModal from './components/StatsModal.jsx'
import StreamModal from './components/StreamModal.jsx'
import ExportObjectsModal from './components/ExportObjectsModal.jsx'

// 工作区持久化：刷新后恢复文件/过滤器/布局
const WS_KEY = 'wsa.workspace.v1'
function loadWorkspace() {
  try { return JSON.parse(localStorage.getItem(WS_KEY) || '{}') } catch { return {} }
}

export default function App() {
  const _ws = loadWorkspace()
  const [pcapFile, setPcapFile] = useState(_ws.pcapFile || '')
  const [filter, setFilter] = useState(_ws.filter || '')
  const [appliedFilter, setAppliedFilter] = useState(_ws.appliedFilter || '')
  const [packets, setPackets] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(_ws.page || 0)
  const [pageSize] = useState(100)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState(null)
  const [detail, setDetail] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [checked, setChecked] = useState(new Set())

  // 时间列显示格式：relative | absolute | delta
  const [timeFormat, setTimeFormat] = useState(_ws.timeFormat || 'relative')

  // AI 总结独立面板
  const [summary, setSummary] = useState(null)
  // 统计弹窗
  const [showStats, setShowStats] = useState(false)
  // 追踪流弹窗：{packetNumber} | null
  const [streamTarget, setStreamTarget] = useState(null)
  // 导出对象弹窗
  const [showExport, setShowExport] = useState(false)

  // ---- 实时抓包（直接在主表格显示，非独立弹窗）----
  // liveStatus: null(未开启) | connecting | running | stopped | error
  const [liveStatus, setLiveStatus] = useState(null)
  const [liveCount, setLiveCount] = useState(0)
  const [liveFile, setLiveFile] = useState('')
  const [liveError, setLiveError] = useState('')
  const liveWsRef = useRef(null)
  // 批量缓冲：高频包先入缓冲，requestAnimationFrame 节流刷入，避免页面闪烁
  const liveBufRef = useRef([])
  const liveFlushTimer = useRef(null)

  // 可调整布局：右栏宽度、详情栏高度比例
  const [rightWidth, setRightWidth] = useState(_ws.rightWidth || 380)
  const [tableRatio, setTableRatio] = useState(_ws.tableRatio || 0.6)
  const mainRef = useRef(null)
  const leftRef = useRef(null)

  // 工作区变更时持久化
  useEffect(() => {
    localStorage.setItem(WS_KEY, JSON.stringify({
      pcapFile, filter, appliedFilter, page, timeFormat, rightWidth, tableRatio,
    }))
  }, [pcapFile, filter, appliedFilter, page, timeFormat, rightWidth, tableRatio])

  const loadPackets = useCallback(async (file, filt, pg, tf = timeFormat) => {
    if (!file) return
    setLoading(true)
    setError('')
    try {
      const [listData, countData] = await Promise.all([
        api.listPackets({ file, filter: filt, offset: pg * pageSize, limit: pageSize, timeFormat: tf }),
        api.countPackets({ file, filter: filt }),
      ])
      setPackets(listData.packets)
      setTotal(countData.count)
    } catch (e) {
      setError(e.message)
      setPackets([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }, [pageSize, timeFormat])

  const handleOpenFile = useCallback((file) => {
    setPcapFile(file)
    setPage(0)
    setSelected(null)
    setDetail(null)
    setChecked(new Set())
    setSummary(null)
    setStreamTarget(null)
    loadPackets(file, appliedFilter, 0)
  }, [appliedFilter, loadPackets])

  // 挂载时恢复上次工作区（打开的文件 + 过滤器）
  const _restored = useRef(false)
  useEffect(() => {
    if (_restored.current || !pcapFile) return
    _restored.current = true
    loadPackets(pcapFile, appliedFilter, page)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // ---- 实时抓包：批量刷入（rAF 节流，防闪烁）----
  const flushLiveBuffer = useCallback(() => {
    liveFlushTimer.current = null
    const buf = liveBufRef.current
    if (!buf.length) return
    liveBufRef.current = []
    // 新包追加到顶部，最多保留 2000 行
    setPackets((prev) => [...buf.reverse(), ...prev].slice(0, 2000))
  }, [])

  const scheduleLiveFlush = useCallback(() => {
    if (liveFlushTimer.current) return
    liveFlushTimer.current = requestAnimationFrame(flushLiveBuffer)
  }, [flushLiveBuffer])

  // 启动实时抓包（带「预连接」重试，解决首次必失败问题）
  const handleStartLive = useCallback((iface, bpf) => {
    // 关闭旧连接
    if (liveWsRef.current) { try { liveWsRef.current.close() } catch { /* */ } }
    setLiveStatus('connecting')
    setLiveError('')
    setLiveCount(0)
    setPackets([])
    setSelected(null)
    setDetail(null)
    setChecked(new Set())

    let attempt = 0
    const MAX_ATTEMPT = 2  // 首次失败自动重试 1 次

    const connect = () => {
      attempt += 1
      const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
      const url = `${proto}://${window.location.host}/api/live/capture?interface=${encodeURIComponent(iface)}&bpf_filter=${encodeURIComponent(bpf || '')}`
      const ws = new WebSocket(url)
      liveWsRef.current = ws
      let gotStarted = false

      ws.onopen = () => { /* 等 started 消息 */ }
      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data)
          if (msg.type === 'started') {
            gotStarted = true
            setLiveStatus('running')
            setLiveFile(msg.file || '')
          } else if (msg.type === 'packet') {
            liveBufRef.current.push(msg.packet)
            setLiveCount(msg.count)
            scheduleLiveFlush()
          } else if (msg.type === 'done') {
            setLiveStatus('stopped')
            if (msg.file) setLiveFile(msg.file)
            flushLiveBuffer()
          } else if (msg.type === 'error') {
            setLiveError(msg.message)
            setLiveStatus('error')
          }
        } catch { /* ignore */ }
      }
      ws.onerror = () => {
        if (!gotStarted && attempt < MAX_ATTEMPT) {
          // 预连接失败（tshark 首次初始化慢），自动重试
          setTimeout(connect, 300)
        } else {
          setLiveError('WebSocket 连接失败（请确认管理员权限运行，并选择有流量的网卡）')
          setLiveStatus('error')
        }
      }
      ws.onclose = () => {
        setLiveStatus((s) => (s === 'running' || s === 'connecting' ? 'stopped' : s))
        flushLiveBuffer()
      }
    }
    connect()
  }, [scheduleLiveFlush, flushLiveBuffer])

  // 停止实时抓包
  const handleStopLive = useCallback(() => {
    if (liveWsRef.current && liveWsRef.current.readyState === WebSocket.OPEN) {
      liveWsRef.current.send(JSON.stringify({ action: 'stop' }))
    }
    flushLiveBuffer()
    setLiveStatus('stopped')
  }, [flushLiveBuffer])

  // 退出实时模式（加载抓到的文件到主界面，回到文件分析模式）
  const handleFinishLive = useCallback(() => {
    const file = liveFile
    handleStopLive()
    setLiveStatus(null)
    if (file) handleOpenFile(file)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [liveFile, handleStopLive])

  // 关闭实时模式（不加载文件）
  const handleCloseLive = useCallback(() => {
    handleStopLive()
    setLiveStatus(null)
    setPackets([])
    setLiveCount(0)
  }, [handleStopLive])

  // 卸载时关闭连接 + 清 rAF
  useEffect(() => () => {
    liveWsRef.current?.close()
    if (liveFlushTimer.current) cancelAnimationFrame(liveFlushTimer.current)
  }, [])

  const handleApplyFilter = useCallback(() => {
    setAppliedFilter(filter)
    setPage(0)
    setSelected(null)
    setDetail(null)
    setChecked(new Set())
    loadPackets(pcapFile, filter, 0)
  }, [filter, pcapFile, loadPackets])

  const handlePageChange = useCallback((newPage) => {
    setPage(newPage)
    loadPackets(pcapFile, appliedFilter, newPage)
  }, [pcapFile, appliedFilter, loadPackets])

  const handleSelect = useCallback(async (pkt) => {
    setSelected(pkt)
    setDetailLoading(true)
    try {
      const d = await api.packetDetail({ file: pcapFile, number: pkt.number })
      setDetail(d)
    } catch (e) {
      setDetail({ number: pkt.number, row: pkt, tree: [], hex: [], raw: `加载失败: ${e.message}` })
    } finally {
      setDetailLoading(false)
    }
  }, [pcapFile])

  const handleAiFilter = useCallback((expr) => {
    setFilter(expr)
    setAppliedFilter(expr)
    setPage(0)
    setSelected(null)
    setDetail(null)
    setChecked(new Set())
    loadPackets(pcapFile, expr, 0)
  }, [pcapFile, loadPackets])

  // 右键菜单「作为过滤器应用」：与现有过滤器以 and 叠加（更接近 Wireshark 行为）
  const handleAppendFilter = useCallback((expr) => {
    const merged = appliedFilter ? `${appliedFilter} and ${expr}` : expr
    handleAiFilter(merged)
  }, [appliedFilter, handleAiFilter])

  // 右键菜单「追踪流」
  const handleFollowStream = useCallback((pkt, _proto) => {
    setStreamTarget({ packetNumber: pkt.number })
  }, [])

  // 时间格式切换
  const handleTimeFormatChange = useCallback((tf) => {
    setTimeFormat(tf)
    if (pcapFile) loadPackets(pcapFile, appliedFilter, page, tf)
  }, [pcapFile, appliedFilter, page, loadPackets])

  const handleCheck = useCallback((number, isChecked) => {
    setChecked((prev) => {
      const next = new Set(prev)
      if (isChecked) next.add(number)
      else next.delete(number)
      return next
    })
  }, [])

  const checkedPackets = packets.filter((p) => checked.has(p.number))

  // 拖拽：右栏宽度
  const handleRightDrag = useCallback((clientX) => {
    const rect = mainRef.current?.getBoundingClientRect()
    if (!rect) return
    const newWidth = Math.min(Math.max(rect.right - clientX, 260), rect.width - 400)
    setRightWidth(newWidth)
  }, [])

  // 拖拽：表格/详情高度比例
  const handleVerticalDrag = useCallback((clientY) => {
    const rect = leftRef.current?.getBoundingClientRect()
    if (!rect) return
    const ratio = (clientY - rect.top) / rect.height
    setTableRatio(Math.min(Math.max(ratio, 0.2), 0.85))
  }, [])

  return (
    <div className="app">
      <Toolbar
        pcapFile={pcapFile}
        onOpenFile={handleOpenFile}
        filter={filter}
        onFilterChange={setFilter}
        onApplyFilter={handleApplyFilter}
        loading={loading}
        onShowStats={() => setShowStats(true)}
        onShowExport={() => setShowExport(true)}
        onStartLive={handleStartLive}
        timeFormat={timeFormat}
        onTimeFormatChange={handleTimeFormatChange}
        appliedFilter={appliedFilter}
      />

      {/* 实时抓包状态条（直接在主界面显示，非独立页面） */}
      {liveStatus && (
        <div className={`live-bar live-bar-${liveStatus}`}>
          <span className="live-bar-icon">
            {liveStatus === 'running' ? '🔴' : liveStatus === 'connecting' ? '⏳' : liveStatus === 'error' ? '⚠' : '⏹'}
          </span>
          <span className="live-bar-text">
            {liveStatus === 'running' && `实时抓包中 · 已捕获 ${liveCount} 个包`}
            {liveStatus === 'connecting' && '正在连接并启动抓包…'}
            {liveStatus === 'stopped' && `已停止 · 共 ${liveCount} 个包`}
            {liveStatus === 'error' && (liveError || '抓包出错')}
          </span>
          <div className="live-bar-actions">
            {liveStatus === 'running' && (
              <button className="btn btn-sm btn-danger" onClick={handleStopLive}>■ 停止</button>
            )}
            {(liveStatus === 'stopped' || liveStatus === 'error') && liveCount > 0 && (
              <button className="btn btn-sm btn-primary" onClick={handleFinishLive}>✓ 加载分析</button>
            )}
            <button className="btn btn-sm" onClick={handleCloseLive}>✕ 退出实时模式</button>
          </div>
        </div>
      )}

      <div className="main" ref={mainRef}>
        <div className="left-pane" ref={leftRef} style={{ width: `calc(100% - ${rightWidth}px)` }}>
          <div className="table-pane" style={{ height: `${tableRatio * 100}%` }}>
            <PacketTable
              packets={packets}
              loading={loading || liveStatus === 'connecting'}
              error={error}
              selected={selected}
              onSelect={handleSelect}
              checked={checked}
              onCheck={handleCheck}
              page={page}
              pageSize={pageSize}
              total={total}
              onPageChange={handlePageChange}
              pcapFile={pcapFile}
              liveMode={!!liveStatus}
              onApplyFilterExpr={handleAppendFilter}
              onFollowStream={handleFollowStream}
            />
          </div>
          <Splitter direction="column" onDrag={handleVerticalDrag} />
          <div className="detail-pane" style={{ height: `${(1 - tableRatio) * 100}%` }}>
            <PacketDetail
              detail={detail}
              loading={detailLoading}
              selected={selected}
              onApplyFilterExpr={handleAppendFilter}
            />
          </div>
        </div>

        <Splitter direction="row" onDrag={handleRightDrag} />

        <div className="right-pane" style={{ width: `${rightWidth}px` }}>
          <ChatPanel
            pcapFile={pcapFile}
            currentFilter={appliedFilter}
            onApplyFilter={handleAiFilter}
            checkedPackets={checkedPackets}
            onSummarize={setSummary}
          />
        </div>
      </div>

      {summary && (
        <SummaryPanel
          summary={summary}
          packets={checkedPackets}
          pcapFile={pcapFile}
          filterExpr={appliedFilter}
          onClose={() => setSummary(null)}
        />
      )}

      {showStats && (
        <StatsModal
          pcapFile={pcapFile}
          filter={appliedFilter}
          onClose={() => setShowStats(false)}
        />
      )}

      {streamTarget && (
        <StreamModal
          pcapFile={pcapFile}
          packetNumber={streamTarget.packetNumber}
          onClose={() => setStreamTarget(null)}
        />
      )}

      {showExport && (
        <ExportObjectsModal
          pcapFile={pcapFile}
          onClose={() => setShowExport(false)}
        />
      )}
    </div>
  )
}

import React, { useState, useCallback, useRef } from 'react'
import { api } from './api.js'
import Toolbar from './components/Toolbar.jsx'
import PacketTable from './components/PacketTable.jsx'
import PacketDetail from './components/PacketDetail.jsx'
import ChatPanel from './components/ChatPanel.jsx'
import Splitter from './components/Splitter.jsx'
import SummaryPanel from './components/SummaryPanel.jsx'
import StatsModal from './components/StatsModal.jsx'
import StreamModal from './components/StreamModal.jsx'

export default function App() {
  const [pcapFile, setPcapFile] = useState('')
  const [filter, setFilter] = useState('')
  const [appliedFilter, setAppliedFilter] = useState('')
  const [packets, setPackets] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(0)
  const [pageSize] = useState(100)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState(null)
  const [detail, setDetail] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [checked, setChecked] = useState(new Set())

  // 时间列显示格式：relative | absolute | delta
  const [timeFormat, setTimeFormat] = useState('relative')

  // AI 总结独立面板
  const [summary, setSummary] = useState(null)
  // 统计弹窗
  const [showStats, setShowStats] = useState(false)
  // 追踪流弹窗：{packetNumber} | null
  const [streamTarget, setStreamTarget] = useState(null)

  // 可调整布局：右栏宽度、详情栏高度比例
  const [rightWidth, setRightWidth] = useState(380)
  const [tableRatio, setTableRatio] = useState(0.6) // 表格占左栏高度比例
  const mainRef = useRef(null)
  const leftRef = useRef(null)

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
        timeFormat={timeFormat}
        onTimeFormatChange={handleTimeFormatChange}
        appliedFilter={appliedFilter}
      />

      <div className="main" ref={mainRef}>
        <div className="left-pane" ref={leftRef} style={{ width: `calc(100% - ${rightWidth}px)` }}>
          <div className="table-pane" style={{ height: `${tableRatio * 100}%` }}>
            <PacketTable
              packets={packets}
              loading={loading}
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
    </div>
  )
}

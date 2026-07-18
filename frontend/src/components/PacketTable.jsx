import React, { useState, useEffect, useRef, useCallback } from 'react'
import { useContextMenu } from './ContextMenu.jsx'

// 协议 -> 颜色（仿 Wireshark 配色，深色主题下的柔和版本）
const PROTO_COLORS = {
  TCP: '#7aa2f7', UDP: '#9ece6a', HTTP: '#e0af68', HTTPS: '#e0af68',
  DNS: '#bb9af7', TLS: '#f7768e', SSL: '#f7768e', ICMP: '#7dcfff',
  ARP: '#ff9e64', HTTP2: '#e0af68', QUIC: '#73daca',
}

function protoColor(proto) {
  const p = (proto || '').toUpperCase()
  for (const key of Object.keys(PROTO_COLORS)) {
    if (p.includes(key)) return PROTO_COLORS[key]
  }
  return '#a9b1d6'
}

// ---- 列定义与列宽持久化 ----
const COLUMNS = [
  { key: 'check', label: '', defaultWidth: 30, resizable: false },
  { key: 'no', label: 'No.', defaultWidth: 60 },
  { key: 'time', label: 'Time', defaultWidth: 110 },
  { key: 'src', label: 'Source', defaultWidth: 130 },
  { key: 'dst', label: 'Destination', defaultWidth: 130 },
  { key: 'proto', label: 'Protocol', defaultWidth: 80 },
  { key: 'len', label: 'Length', defaultWidth: 65 },
  { key: 'info', label: 'Info', defaultWidth: null }, // 自适应剩余宽度
]

const LS_KEY = 'wsa.colWidths.v1'

function loadWidths() {
  try {
    const saved = JSON.parse(localStorage.getItem(LS_KEY) || '{}')
    const widths = {}
    for (const col of COLUMNS) {
      widths[col.key] = saved[col.key] || col.defaultWidth
    }
    return widths
  } catch {
    return Object.fromEntries(COLUMNS.map((c) => [c.key, c.defaultWidth]))
  }
}

// 数据包列表表格（Wireshark 主窗口风格）
// 支持：右键上下文菜单（作为过滤器应用/追踪流）、键盘 ↑↓ 导航、列宽拖拽
export default function PacketTable({
  packets, loading, error, selected, onSelect,
  checked, onCheck, page, pageSize, total, onPageChange, pcapFile,
  onApplyFilterExpr, onFollowStream,
}) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  const { menu, openMenu } = useContextMenu()
  const wrapRef = useRef(null)

  // ---- 列宽 ----
  const [widths, setWidths] = useState(loadWidths)
  const dragRef = useRef(null) // {key, startX, startWidth}

  useEffect(() => {
    localStorage.setItem(LS_KEY, JSON.stringify(widths))
  }, [widths])

  const startResize = useCallback((e, key) => {
    e.preventDefault()
    e.stopPropagation()
    dragRef.current = { key, startX: e.clientX, startWidth: widths[key] }
    const onMove = (ev) => {
      const d = dragRef.current
      if (!d) return
      const newW = Math.max(40, d.startWidth + (ev.clientX - d.startX))
      setWidths((w) => ({ ...w, [d.key]: newW }))
    }
    const onUp = () => {
      dragRef.current = null
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseup', onUp)
    }
    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup', onUp)
  }, [widths])

  const resetWidths = useCallback(() => {
    setWidths(Object.fromEntries(COLUMNS.map((c) => [c.key, c.defaultWidth])))
  }, [])

  // ---- 键盘导航：↑↓ 切换选中包 ----
  useEffect(() => {
    const onKey = (e) => {
      // 输入框聚焦时不劫持按键
      const tag = document.activeElement?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA') return
      if (!packets.length) return
      if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return
      e.preventDefault()
      const idx = packets.findIndex((p) => p.number === selected?.number)
      let next
      if (idx === -1) {
        next = e.key === 'ArrowDown' ? packets[0] : packets[packets.length - 1]
      } else if (e.key === 'ArrowDown') {
        next = packets[Math.min(idx + 1, packets.length - 1)]
      } else {
        next = packets[Math.max(idx - 1, 0)]
      }
      if (next && next.number !== selected?.number) onSelect(next)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [packets, selected, onSelect])

  // 选中行滚动到可视区域
  useEffect(() => {
    if (!selected) return
    wrapRef.current
      ?.querySelector('.row-selected')
      ?.scrollIntoView({ block: 'nearest' })
  }, [selected])

  // ---- 行右键菜单 ----
  const onRowContextMenu = useCallback((e, p) => {
    onSelect(p)
    const isIp = p.source && p.source.includes('.') || p.source?.includes(':')
    const items = [
      {
        label: `作为过滤器应用：ip.addr == ${p.source}`,
        icon: '🔍',
        disabled: !isIp,
        onClick: () => onApplyFilterExpr?.(`ip.addr == ${p.source}`),
      },
      {
        label: `过滤会话：${p.source} ↔ ${p.destination}`,
        icon: '⇄',
        disabled: !isIp,
        onClick: () => onApplyFilterExpr?.(
          `(ip.addr == ${p.source} and ip.addr == ${p.destination})`,
        ),
      },
      {
        label: `过滤协议：${p.protocol}`,
        icon: '🏷',
        disabled: !p.protocol,
        onClick: () => onApplyFilterExpr?.(p.protocol.toLowerCase()),
      },
      { divider: true },
      {
        label: '追踪 TCP 流',
        icon: '🔀',
        onClick: () => onFollowStream?.(p, 'tcp'),
      },
      {
        label: '追踪 UDP 流',
        icon: '🔀',
        onClick: () => onFollowStream?.(p, 'udp'),
      },
      { divider: true },
      {
        label: `复制 Info`,
        icon: '📋',
        onClick: () => navigator.clipboard?.writeText(p.info || ''),
      },
    ]
    openMenu(e, items)
  }, [onSelect, onApplyFilterExpr, onFollowStream, openMenu])

  if (!pcapFile) {
    return (
      <div className="table-empty">
        <div className="empty-icon">🦈</div>
        <p>请通过顶部工具栏 <b>抓包</b>、<b>上传 pcap</b> 或打开 <b>历史文件</b> 开始分析</p>
      </div>
    )
  }

  const colStyle = (key) => {
    const w = widths[key]
    return w ? { width: w, minWidth: w, maxWidth: w } : {}
  }

  return (
    <div className="packet-table-wrap" ref={wrapRef}>
      <table className="packet-table">
        <thead>
          <tr>
            {COLUMNS.map((col) => (
              <th key={col.key} style={colStyle(col.key)} className={`col-${col.key}`}>
                <span>{col.label}</span>
                {col.resizable !== false && (
                  <span
                    className="col-resizer"
                    onMouseDown={(e) => startResize(e, col.key)}
                    onDoubleClick={resetWidths}
                    title="拖拽调整列宽 · 双击重置全部"
                  />
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {packets.map((p) => {
            const isSelected = selected?.number === p.number
            return (
              <tr
                key={p.number}
                className={isSelected ? 'row-selected' : ''}
                onClick={() => onSelect(p)}
                onContextMenu={(e) => onRowContextMenu(e, p)}
              >
                <td className="col-check" style={colStyle('check')} onClick={(e) => e.stopPropagation()}>
                  <input
                    type="checkbox"
                    checked={checked.has(p.number)}
                    onChange={(e) => onCheck(p.number, e.target.checked)}
                  />
                </td>
                <td className="col-no" style={colStyle('no')}>{p.number}</td>
                <td className="col-time" style={colStyle('time')}>{p.time}</td>
                <td className="col-src" style={colStyle('src')}>{p.source}</td>
                <td className="col-dst" style={colStyle('dst')}>{p.destination}</td>
                <td className="col-proto" style={{ ...colStyle('proto'), color: protoColor(p.protocol) }}>
                  {p.protocol}
                </td>
                <td className="col-len" style={colStyle('len')}>{p.length}</td>
                <td className="col-info">{p.info}</td>
              </tr>
            )
          })}
          {!loading && packets.length === 0 && (
            <tr><td colSpan="8" className="table-empty-row">
              {error ? `加载失败：${error}` : '没有匹配的数据包'}
            </td></tr>
          )}
        </tbody>
      </table>

      {loading && <div className="table-loading">加载中…</div>}

      <div className="pagination">
        <button className="btn btn-sm" disabled={page === 0} onClick={() => onPageChange(0)}>«</button>
        <button className="btn btn-sm" disabled={page === 0} onClick={() => onPageChange(page - 1)}>‹ 上一页</button>
        <span className="page-info">
          第 {page + 1} / {totalPages} 页 · 共 {total} 个包
          <span className="kbd-hint">↑↓ 切换包 · 右键更多操作</span>
        </span>
        <button className="btn btn-sm" disabled={page >= totalPages - 1} onClick={() => onPageChange(page + 1)}>下一页 ›</button>
        <button className="btn btn-sm" disabled={page >= totalPages - 1} onClick={() => onPageChange(totalPages - 1)}>»</button>
      </div>

      {menu}
    </div>
  )
}

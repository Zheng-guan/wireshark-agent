import React, { useState, useEffect, useRef, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import { api } from '../api.js'
import { useContextMenu } from './ContextMenu.jsx'

// 从协议树节点的显示文本中提取「字段名 == 值」形式的过滤表达式。
// Wireshark 树节点文本形如 "Source Address: 192.168.1.1" 或
// "Window scale: 7 (multiply by 128)"，无法直接得到字段缩写，
// 因此退而求其次：若节点带 value，则生成 contains 语义提示；
// 更精确的表达式由用户通过右键「复制显示文本」自行加工。
// 这里实现常见字段的启发式映射（IP/端口/协议标志等）。
function guessFilterExpr(node, ancestors) {
  const text = `${node.name}${node.value ? `: ${node.value}` : ''}`
  const layer = (ancestors[0]?.name || '').toLowerCase()

  // "Source Address: x" / "Destination Address: x"
  if (/source address/i.test(node.name) && node.value) {
    return layer.includes('ipv6') ? `ipv6.src == ${node.value}` : `ip.src == ${node.value}`
  }
  if (/destination address/i.test(node.name) && node.value) {
    return layer.includes('ipv6') ? `ipv6.dst == ${node.value}` : `ip.dst == ${node.value}`
  }
  // "Source Port: 80" / "Destination Port: 443"
  if (/source port/i.test(node.name) && node.value) {
    return `${layer === 'udp' ? 'udp' : 'tcp'}.srcport == ${node.value}`
  }
  if (/destination port/i.test(node.name) && node.value) {
    return `${layer === 'udp' ? 'udp' : 'tcp'}.dstport == ${node.value}`
  }
  // "Stream index: 0"
  if (/stream index/i.test(node.name) && node.value !== '') {
    return `${layer === 'udp' ? 'udp' : 'tcp'}.stream == ${node.value}`
  }
  return null
}

// AI 字段解释气泡（Popover）
function ExplainPopover({ anchor, content, loading, onClose }) {
  const ref = useRef(null)
  useEffect(() => {
    const onDown = (e) => {
      if (ref.current && !ref.current.contains(e.target)) onClose()
    }
    const onKey = (e) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [onClose])

  // 防止气泡超出视口
  const W = 340
  const x = Math.min(anchor.x, window.innerWidth - W - 16)
  const y = Math.min(anchor.y, window.innerHeight - 260)

  return (
    <div ref={ref} className="explain-popover" style={{ left: x, top: y, width: W }}>
      <div className="explain-header">
        <span>🤖 AI 字段解释</span>
        <button className="explain-close" onClick={onClose}>✕</button>
      </div>
      <div className="explain-body markdown-body">
        {loading ? <span className="explain-loading">思考中…</span> : <ReactMarkdown>{content}</ReactMarkdown>}
      </div>
    </div>
  )
}

// 协议树节点（可折叠 + 右键菜单 + AI 解释）
function TreeNode({ node, depth = 0, ancestors = [], onApplyFilterExpr, onExplain }) {
  const [open, setOpen] = useState(depth < 1)
  const hasChildren = node.children && node.children.length > 0
  const { menu, openMenu } = useContextMenu()

  const path = [...ancestors, node]
  const displayText = `${node.name}${node.value ? `: ${node.value}` : ''}`

  const onContextMenu = (e) => {
    e.stopPropagation()
    const expr = guessFilterExpr(node, ancestors)
    const items = [
      {
        label: '作为过滤器应用',
        icon: '🔍',
        disabled: !expr,
        hint: expr || undefined,
        onClick: () => expr && onApplyFilterExpr?.(expr),
      },
      {
        label: '复制显示文本',
        icon: '📋',
        onClick: () => navigator.clipboard?.writeText(displayText),
      },
      { divider: true },
      {
        label: 'AI 解释该字段',
        icon: '🤖',
        onClick: () => onExplain(e, node, path),
      },
    ]
    openMenu(e, items)
  }

  return (
    <div className="tree-node">
      <div
        className={`tree-label ${hasChildren ? 'tree-parent' : 'tree-leaf'}`}
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
        onClick={() => hasChildren && setOpen(!open)}
        onContextMenu={onContextMenu}
        title="右键：过滤器 / AI 解释"
      >
        <span className="tree-arrow">{hasChildren ? (open ? '▾' : '▸') : '·'}</span>
        <span className="tree-name">{node.name}</span>
        {node.value && <span className="tree-value">{node.value}</span>}
        <button
          className="tree-explain-btn"
          title="AI 解释该字段"
          onClick={(e) => { e.stopPropagation(); onExplain(e, node, path) }}
        >
          ?
        </button>
      </div>
      {open && hasChildren && (
        <div className="tree-children">
          {node.children.map((child, i) => (
            <TreeNode
              key={i}
              node={child}
              depth={depth + 1}
              ancestors={path}
              onApplyFilterExpr={onApplyFilterExpr}
              onExplain={onExplain}
            />
          ))}
        </div>
      )}
      {menu}
    </div>
  )
}

// 数据包详情面板：协议树 + Hex 视图 + 原始文本
export default function PacketDetail({ detail, loading, selected, onApplyFilterExpr }) {
  const [tab, setTab] = useState('tree')
  const [explain, setExplain] = useState(null) // {anchor, content, loading}

  const handleExplain = useCallback(async (e, node, path) => {
    const anchor = { x: e.clientX + 8, y: e.clientY + 8 }
    setExplain({ anchor, content: '', loading: true })
    try {
      const layer = path[0]?.name || ''
      const fieldPath = path.map((n) => n.name).join(' > ')
      const r = await api.explainField({
        layer,
        field_path: fieldPath,
        field_name: node.name,
        field_value: node.value || '',
      })
      setExplain((prev) => prev && { ...prev, content: r.explanation, loading: false })
    } catch (err) {
      setExplain((prev) => prev && { ...prev, content: `解释失败：${err.message}`, loading: false })
    }
  }, [])

  // 切换数据包时关闭气泡
  useEffect(() => { setExplain(null) }, [selected?.number])

  if (!selected) {
    return (
      <div className="detail-empty">
        <p>点击上方表格中的数据包查看协议树详情</p>
      </div>
    )
  }

  return (
    <div className="packet-detail">
      <div className="detail-tabs">
        <button
          className={`tab ${tab === 'tree' ? 'tab-active' : ''}`}
          onClick={() => setTab('tree')}
        >
          协议树
        </button>
        <button
          className={`tab ${tab === 'hex' ? 'tab-active' : ''}`}
          onClick={() => setTab('hex')}
        >
          Hex
        </button>
        <button
          className={`tab ${tab === 'raw' ? 'tab-active' : ''}`}
          onClick={() => setTab('raw')}
        >
          原始详情
        </button>
        <span className="detail-title">
          {loading ? '加载中…' : `数据包 #${selected.number}`}
        </span>
      </div>

      <div className="detail-body">
        {loading && <div className="detail-loading">解析中…</div>}

        {!loading && detail && tab === 'tree' && (
          <div className="tree-view">
            {detail.tree.length === 0 && <p className="detail-empty">无协议树数据</p>}
            {detail.tree.map((layer, i) => (
              <TreeNode
                key={i}
                node={layer}
                depth={0}
                ancestors={[]}
                onApplyFilterExpr={onApplyFilterExpr}
                onExplain={handleExplain}
              />
            ))}
          </div>
        )}

        {!loading && detail && tab === 'hex' && (
          <div className="hex-view">
            {(!detail.hex || detail.hex.length === 0) && (
              <p className="detail-empty">无 Hex 数据</p>
            )}
            {detail.hex && detail.hex.map((line, i) => (
              <div key={i} className="hex-line">
                <span className="hex-offset">{line.offset}</span>
                <span className="hex-bytes">{line.hex}</span>
                <span className="hex-ascii">{line.ascii}</span>
              </div>
            ))}
          </div>
        )}

        {!loading && detail && tab === 'raw' && (
          <pre className="raw-view">{detail.raw}</pre>
        )}
      </div>

      {explain && (
        <ExplainPopover
          anchor={explain.anchor}
          content={explain.content}
          loading={explain.loading}
          onClose={() => setExplain(null)}
        />
      )}
    </div>
  )
}

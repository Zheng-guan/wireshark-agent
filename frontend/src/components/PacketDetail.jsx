import React, { useState } from 'react'

// 协议树节点（可折叠）
function TreeNode({ node, depth = 0 }) {
  const [open, setOpen] = useState(depth < 1)
  const hasChildren = node.children && node.children.length > 0

  return (
    <div className="tree-node">
      <div
        className={`tree-label ${hasChildren ? 'tree-parent' : 'tree-leaf'}`}
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
        onClick={() => hasChildren && setOpen(!open)}
      >
        <span className="tree-arrow">{hasChildren ? (open ? '▾' : '▸') : '·'}</span>
        <span className="tree-name">{node.name}</span>
        {node.value && <span className="tree-value">{node.value}</span>}
      </div>
      {open && hasChildren && (
        <div className="tree-children">
          {node.children.map((child, i) => (
            <TreeNode key={i} node={child} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  )
}

// 数据包详情面板：协议树 + Hex 视图 + 原始文本
export default function PacketDetail({ detail, loading, selected }) {
  const [tab, setTab] = useState('tree')

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
              <TreeNode key={i} node={layer} depth={0} />
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
    </div>
  )
}

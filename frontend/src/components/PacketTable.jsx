import React from 'react'

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

// 数据包列表表格（Wireshark 主窗口风格）
export default function PacketTable({
  packets, loading, error, selected, onSelect,
  checked, onCheck, page, pageSize, total, onPageChange, pcapFile,
}) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize))

  if (!pcapFile) {
    return (
      <div className="table-empty">
        <div className="empty-icon">🦈</div>
        <p>请通过顶部工具栏 <b>抓包</b>、<b>上传 pcap</b> 或打开 <b>历史文件</b> 开始分析</p>
      </div>
    )
  }

  return (
    <div className="packet-table-wrap">
      <table className="packet-table">
        <thead>
          <tr>
            <th className="col-check"></th>
            <th className="col-no">No.</th>
            <th className="col-time">Time</th>
            <th className="col-src">Source</th>
            <th className="col-dst">Destination</th>
            <th className="col-proto">Protocol</th>
            <th className="col-len">Length</th>
            <th className="col-info">Info</th>
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
              >
                <td className="col-check" onClick={(e) => e.stopPropagation()}>
                  <input
                    type="checkbox"
                    checked={checked.has(p.number)}
                    onChange={(e) => onCheck(p.number, e.target.checked)}
                  />
                </td>
                <td className="col-no">{p.number}</td>
                <td className="col-time">{p.time}</td>
                <td className="col-src">{p.source}</td>
                <td className="col-dst">{p.destination}</td>
                <td className="col-proto" style={{ color: protoColor(p.protocol) }}>
                  {p.protocol}
                </td>
                <td className="col-len">{p.length}</td>
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
        </span>
        <button className="btn btn-sm" disabled={page >= totalPages - 1} onClick={() => onPageChange(page + 1)}>下一页 ›</button>
        <button className="btn btn-sm" disabled={page >= totalPages - 1} onClick={() => onPageChange(totalPages - 1)}>»</button>
      </div>
    </div>
  )
}

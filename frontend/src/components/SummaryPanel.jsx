import React from 'react'
import ReactMarkdown from 'react-markdown'
import { api } from '../api.js'

// AI 总结独立展示面板：以美观的 Markdown 卡片形式呈现诊断报告，
// 不再与右侧聊天控制台混用。支持导出为 HTML 报告。
export default function SummaryPanel({ summary, packets, pcapFile, filterExpr, onClose }) {
  const [exporting, setExporting] = React.useState(false)

  const doExport = async () => {
    setExporting(true)
    try {
      const html = await api.exportReport({
        title: '网络分析报告',
        summary,
        packets,
        pcap_file: pcapFile,
        filter_expr: filterExpr,
      })
      const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `report_${Date.now()}.html`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      alert(`导出失败: ${e.message}`)
    } finally {
      setExporting(false)
    }
  }

  return (
    <div className="summary-overlay" onClick={onClose}>
      <div className="summary-panel" onClick={(e) => e.stopPropagation()}>
        <div className="summary-header">
          <span className="summary-title">✨ AI 分析报告</span>
          <div className="summary-actions">
            <button className="btn btn-sm btn-accent" onClick={doExport} disabled={exporting}>
              {exporting ? '导出中…' : '⬇ 导出 HTML'}
            </button>
            <button className="btn btn-sm" onClick={onClose}>关闭 ✕</button>
          </div>
        </div>
        <div className="summary-meta">
          <span>📦 {packets.length} 个数据包</span>
          {pcapFile && <span title={pcapFile}>📁 {pcapFile.split(/[\\/]/).pop()}</span>}
          {filterExpr && <span>🔍 {filterExpr}</span>}
        </div>
        <div className="summary-body markdown-body">
          <ReactMarkdown>{summary}</ReactMarkdown>
        </div>
      </div>
    </div>
  )
}

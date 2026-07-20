import React, { useState, useEffect } from 'react'
import { api } from '../api.js'

// 导出对象弹窗：列出 pcap 中可提取的协议对象（HTTP 下载的文件等），支持下载。
export default function ExportObjectsModal({ pcapFile, onClose }) {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [data, setData] = useState(null)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setLoading(true)
      setError('')
      try {
        const d = await api.exportObjects({ file: pcapFile, proto: 'http' })
        if (!cancelled) setData(d)
      } catch (e) {
        if (!cancelled) setError(e.message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [pcapFile])

  const doDownload = (obj) => {
    api.downloadExportedObject({ session: obj.session || data.session, filename: obj.filename })
  }

  return (
    <div className="summary-overlay" onClick={onClose}>
      <div className="summary-panel export-panel" onClick={(e) => e.stopPropagation()}>
        <div className="summary-header">
          <span className="summary-title">📦 导出对象（HTTP）</span>
          <button className="btn btn-sm" onClick={onClose}>关闭 ✕</button>
        </div>
        <div className="summary-body">
          {loading && <p className="detail-empty">正在提取对象…</p>}
          {error && <p className="detail-empty">⚠ {error}</p>}
          {data && (
            <>
              <p className="stats-total">
                共提取到 {data.count} 个对象
                {data.count > 0 && '（点击右侧下载）'}
              </p>
              {data.count === 0 && (
                <p className="detail-empty">
                  该文件中没有可提取的 HTTP 对象。<br/>
                  <small>只有完整的 HTTP 响应（带文件内容）才能被提取。</small>
                </p>
              )}
              <div className="export-list">
                {data.objects.map((obj) => (
                  <div key={obj.id} className="export-item">
                    <span className="export-icon">📄</span>
                    <span className="export-name" title={obj.filename}>{obj.filename}</span>
                    <span className="export-size">{obj.size_kb} KB</span>
                    <button className="btn btn-sm" onClick={() => doDownload(obj)}>⬇ 下载</button>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

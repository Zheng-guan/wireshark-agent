import React, { useState, useEffect } from 'react'
import { api } from '../api.js'

// 协议分布图表弹窗：纯 CSS 水平条形图（无图表库依赖）
export default function StatsModal({ pcapFile, filter, onClose }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const d = await api.protocolDistribution({ file: pcapFile, filter })
        if (!cancelled) setData(d)
      } catch (e) {
        if (!cancelled) setError(e.message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [pcapFile, filter])

  const max = data?.distribution?.length
    ? Math.max(...data.distribution.map((d) => d.count))
    : 1

  return (
    <div className="summary-overlay" onClick={onClose}>
      <div className="summary-panel stats-panel" onClick={(e) => e.stopPropagation()}>
        <div className="summary-header">
          <span className="summary-title">📊 协议分布</span>
          <button className="btn btn-sm" onClick={onClose}>关闭 ✕</button>
        </div>
        <div className="summary-body">
          {loading && <p className="detail-empty">统计中…</p>}
          {error && <p className="detail-empty">加载失败：{error}</p>}
          {data && (
            <>
              <p className="stats-total">共 {data.total} 个数据包</p>
              <div className="bar-chart">
                {data.distribution.map((d) => (
                  <div key={d.protocol} className="bar-row">
                    <span className="bar-label">{d.protocol}</span>
                    <div className="bar-track">
                      <div
                        className="bar-fill"
                        style={{ width: `${(d.count / max) * 100}%` }}
                      />
                    </div>
                    <span className="bar-value">{d.count}</span>
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

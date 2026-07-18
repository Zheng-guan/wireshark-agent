import React, { useEffect, useState, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import { api } from '../api.js'

// 追踪流弹窗：展示完整 TCP/UDP 双向会话内容（仿 Wireshark Follow Stream），
// 客户端/服务端数据分色显示，支持一键 AI 会话级诊断。
export default function StreamModal({ pcapFile, packetNumber, onClose }) {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [stream, setStream] = useState(null) // {proto, index, nodes, segments}
  const [showHexHint, setShowHexHint] = useState(false)

  // AI 诊断
  const [analyzing, setAnalyzing] = useState(false)
  const [analysis, setAnalysis] = useState('')

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setLoading(true)
      setError('')
      try {
        const info = await api.streamInfo({ file: pcapFile, number: packetNumber })
        const data = await api.followStream({
          file: pcapFile, proto: info.proto, index: info.index,
        })
        if (!cancelled) setStream(data)
      } catch (e) {
        if (!cancelled) setError(e.message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [pcapFile, packetNumber])

  const doAnalyze = useCallback(async () => {
    if (!stream) return
    setAnalyzing(true)
    setAnalysis('')
    try {
      const r = await api.analyzeStream({
        proto: stream.proto,
        nodes: stream.nodes,
        segments: stream.segments,
      })
      setAnalysis(r.analysis)
    } catch (e) {
      setAnalysis(`诊断失败：${e.message}`)
    } finally {
      setAnalyzing(false)
    }
  }, [stream])

  const node0 = stream?.nodes?.[0] || '客户端'
  const node1 = stream?.nodes?.[1] || '服务端'

  return (
    <div className="summary-overlay" onClick={onClose}>
      <div className="summary-panel stream-panel" onClick={(e) => e.stopPropagation()}>
        <div className="summary-header">
          <span className="summary-title">
            🔀 追踪 {stream ? stream.proto.toUpperCase() : ''} 流
            {stream && <span className="stream-index">#{stream.index}</span>}
          </span>
          <div className="summary-actions">
            <button
              className="btn btn-sm btn-accent"
              onClick={doAnalyze}
              disabled={analyzing || loading || !!error || !stream?.segments?.length}
              title="让 AI 分析整个会话"
            >
              {analyzing ? '🤖 诊断中…' : '🤖 AI 诊断会话'}
            </button>
            <button className="btn btn-sm" onClick={onClose}>关闭 ✕</button>
          </div>
        </div>

        {stream && (
          <div className="summary-meta">
            <span className="stream-node0">⬤ {node0}</span>
            <span className="stream-arrow">⇄</span>
            <span className="stream-node1">⬤ {node1}</span>
            <span>📦 {stream.segment_count} 段</span>
            {stream.truncated && <span className="stream-truncated">⚠ 内容过长已截断</span>}
          </div>
        )}

        <div className="stream-body">
          {loading && <div className="detail-loading">正在提取流内容…</div>}
          {error && <div className="detail-empty">⚠ {error}</div>}

          {!loading && !error && stream && (
            <>
              {stream.segments.length === 0 && (
                <div className="detail-empty">该流没有可显示的载荷数据（可能仅为握手/控制包）</div>
              )}
              <div className="stream-content">
                {stream.segments.map((seg, i) => (
                  <div key={i} className={`stream-seg ${seg.direction === 0 ? 'stream-seg-c2s' : 'stream-seg-s2c'}`}>
                    <div className="stream-seg-meta">
                      {seg.direction === 0 ? `${node0} → ${node1}` : `${node1} → ${node0}`}
                      <span className="stream-seg-size">{seg.size} B</span>
                    </div>
                    <pre className="stream-seg-data">{seg.data || '(空)'}</pre>
                  </div>
                ))}
              </div>
            </>
          )}

          {(analyzing || analysis) && (
            <div className="stream-analysis">
              <div className="stream-analysis-title">🤖 AI 会话诊断</div>
              {analyzing
                ? <div className="detail-loading">正在分析整个会话…</div>
                : <div className="markdown-body"><ReactMarkdown>{analysis}</ReactMarkdown></div>}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

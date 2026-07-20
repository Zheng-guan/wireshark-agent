import React, { useState, useEffect, useRef, useCallback } from 'react'
import { api } from '../api.js'
import { getFilterCompletions } from '../filterFields.js'

// 单个网卡的实时流量迷你图（最近 N 次采样的接收速率）
function TrafficSpark({ history }) {
  const W = 120
  const H = 28
  const max = Math.max(...history, 1)
  const pts = history
    .map((v, i) => `${(i / Math.max(history.length - 1, 1)) * W},${H - (v / max) * H}`)
    .join(' ')
  return (
    <svg className="traffic-spark" width={W} height={H} viewBox={`0 0 ${W} ${H}`}>
      <polyline points={pts} fill="none" stroke="#9ece6a" strokeWidth="1.5" />
    </svg>
  )
}

function formatBps(bps) {
  if (bps >= 1024 * 1024) return `${(bps / 1024 / 1024).toFixed(1)} MB/s`
  if (bps >= 1024) return `${(bps / 1024).toFixed(1)} KB/s`
  return `${Math.round(bps)} B/s`
}

// 顶部工具栏：文件管理 + 抓包 + 过滤器 + 下载 + 时间格式
export default function Toolbar({
  pcapFile, onOpenFile, filter, onFilterChange, onApplyFilter, loading, onShowStats,
  onShowExport, onStartLive, timeFormat, onTimeFormatChange, appliedFilter,
}) {
  const [files, setFiles] = useState([])
  const [showFiles, setShowFiles] = useState(false)
  const [showCapture, setShowCapture] = useState(false)
  const [interfaces, setInterfaces] = useState([])
  const [trafficHistory, setTrafficHistory] = useState({}) // {name: [recv_bps,...]}
  const [capturing, setCapturing] = useState(false)
  const [captureProgress, setCaptureProgress] = useState(null)
  const [captureMsg, setCaptureMsg] = useState('')
  const fileInputRef = useRef(null)
  const pollRef = useRef(null)
  const filterInputRef = useRef(null)

  const [capForm, setCapForm] = useState({ interface: '', duration: 10, bpf_filter: '' })
  const [capMode, setCapMode] = useState('timed') // timed=定时抓包 | live=实时瀑布流

  // ---- 过滤器：补全 / 校验 / 历史 ----
  const [completions, setCompletions] = useState([])
  const [compIndex, setCompIndex] = useState(-1)
  const [filterValid, setFilterValid] = useState(null) // null=未校验 | true | false
  const [filterMsg, setFilterMsg] = useState('')
  const [showHistory, setShowHistory] = useState(false)
  const validateTimer = useRef(null)
  const HIST_KEY = 'wsa.filterHistory.v1'

  const getHistory = () => {
    try { return JSON.parse(localStorage.getItem(HIST_KEY) || '[]') } catch { return [] }
  }
  const pushHistory = (expr) => {
    if (!expr.trim()) return
    const h = [expr, ...getHistory().filter((x) => x !== expr)].slice(0, 20)
    localStorage.setItem(HIST_KEY, JSON.stringify(h))
  }

  // 输入变化：更新补全 + 防抖校验
  const handleFilterInput = (val) => {
    onFilterChange(val)
    setCompletions(getFilterCompletions(val))
    setCompIndex(-1)
    setShowHistory(false)
    if (validateTimer.current) clearTimeout(validateTimer.current)
    if (!val.trim()) { setFilterValid(null); setFilterMsg(''); return }
    validateTimer.current = setTimeout(async () => {
      try {
        const r = await api.validateFilter(val)
        setFilterValid(r.valid)
        setFilterMsg(r.message || '')
      } catch { setFilterValid(null) }
    }, 500)
  }

  const applyCompletion = (field) => {
    // 用选中字段替换当前输入的最后一个 token
    const newVal = filter.replace(/[A-Za-z0-9_.\-]+$/, field)
    onFilterChange(newVal)
    setCompletions([])
    filterInputRef.current?.focus()
  }

  const doApply = () => {
    pushHistory(filter)
    setCompletions([])
    setShowHistory(false)
    onApplyFilter()
  }

  // 快捷键：按 / 聚焦过滤器输入框
  useEffect(() => {
    const onKey = (e) => {
      const tag = document.activeElement?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA') return
      if (e.key === '/') {
        e.preventDefault()
        filterInputRef.current?.focus()
        filterInputRef.current?.select()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const refreshFiles = async () => {
    try {
      const data = await api.listFiles()
      setFiles(data.files)
    } catch { /* ignore */ }
  }

  useEffect(() => {
    if (showFiles) refreshFiles()
  }, [showFiles])

  // 打开抓包面板：加载网卡（带流量）
  const openCapturePanel = async () => {
    setShowCapture(true)
    try {
      const data = await api.listInterfaces(true)
      setInterfaces(data.interfaces)
      if (data.interfaces.length && !capForm.interface) {
        const preferred = data.interfaces.find((i) => i.alias) || data.interfaces[0]
        setCapForm((f) => ({ ...f, interface: preferred.name }))
      }
    } catch (e) {
      setCaptureMsg(`获取网卡失败: ${e.message}`)
    }
  }

  // 抓包面板打开时，轮询网卡实时流量（每 1.5s）
  useEffect(() => {
    if (!showCapture) return
    let stopped = false
    const tick = async () => {
      try {
        const d = await api.getTraffic()
        if (stopped) return
        setTrafficHistory((prev) => {
          const next = { ...prev }
          for (const nic of d.nics) {
            const arr = next[nic.name] ? [...next[nic.name]] : []
            arr.push(nic.recv_bps)
            next[nic.name] = arr.slice(-20) // 保留最近 20 次
          }
          return next
        })
      } catch { /* ignore */ }
    }
    tick()
    const id = setInterval(tick, 1500)
    return () => { stopped = true; clearInterval(id) }
  }, [showCapture])

  // 启动异步抓包 + 轮询进度
  const doCapture = async () => {
    setCapturing(true)
    setCaptureMsg('正在启动抓包…')
    setCaptureProgress(0)
    try {
      const { task_id } = await api.startCapture({
        interface: capForm.interface,
        duration: Number(capForm.duration) || 10,
        bpf_filter: capForm.bpf_filter || null,
      })
      // 轮询进度
      pollRef.current = setInterval(async () => {
        try {
          const s = await api.captureStatus(task_id)
          setCaptureProgress(s.progress)
          setCaptureMsg(`抓包中… ${Math.round(s.progress * 100)}% · 已捕获 ${s.size_kb} KB`)
          if (s.status === 'done') {
            clearInterval(pollRef.current)
            setCapturing(false)
            setCaptureMsg(`抓包完成：${s.filename}`)
            onOpenFile(s.file)
            setShowCapture(false)
          } else if (s.status === 'error') {
            clearInterval(pollRef.current)
            setCapturing(false)
            setCaptureMsg(`抓包失败：${s.error}`)
          }
        } catch (e) {
          clearInterval(pollRef.current)
          setCapturing(false)
          setCaptureMsg(`查询进度失败：${e.message}`)
        }
      }, 800)
    } catch (e) {
      setCapturing(false)
      setCaptureMsg(`启动抓包失败：${e.message}`)
    }
  }

  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current) }, [])

  const doUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    try {
      const data = await api.uploadFile(file)
      onOpenFile(data.file)
    } catch (err) {
      alert(`上传失败: ${err.message}`)
    } finally {
      e.target.value = ''
    }
  }

  const onFilterKeyDown = (e) => {
    // 补全下拉导航
    if (completions.length) {
      if (e.key === 'ArrowDown') { e.preventDefault(); setCompIndex((i) => Math.min(i + 1, completions.length - 1)); return }
      if (e.key === 'ArrowUp') { e.preventDefault(); setCompIndex((i) => Math.max(i - 1, -1)); return }
      if (e.key === 'Tab' || (e.key === 'Enter' && compIndex >= 0)) {
        e.preventDefault()
        applyCompletion(completions[Math.max(compIndex, 0)].field)
        return
      }
      if (e.key === 'Escape') { setCompletions([]); return }
    }
    if (e.key === 'Enter') doApply()
    // ↑ 翻历史（光标在开头时）
    if (e.key === 'ArrowUp' && e.target.selectionStart === 0) {
      const h = getHistory()
      if (h.length) { setShowHistory(true); setCompletions([]) }
    }
  }

  // 找到当前选中网卡对应的流量历史（按 alias 匹配 psutil 名）
  const currentTraffic = (iface) => {
    if (!iface?.traffic) return null
    return trafficHistory[iface.traffic.name] || null
  }

  return (
    <div className="toolbar">
      <div className="toolbar-row">
        <span className="brand">🦈 Wireshark 智能分析</span>

        <button className="btn" onClick={() => setShowFiles(!showFiles)}>📁 文件</button>
        <button className="btn" onClick={() => fileInputRef.current?.click()}>⬆ 上传</button>
        <input
          ref={fileInputRef} type="file" accept=".pcap,.pcapng,.cap"
          style={{ display: 'none' }} onChange={doUpload}
        />
        <button className="btn btn-primary" onClick={openCapturePanel}>● 抓包</button>
        <button className="btn" onClick={onShowStats} disabled={!pcapFile} title="查看协议分布图">
          📊 统计
        </button>
        <button className="btn" onClick={onShowExport} disabled={!pcapFile} title="提取 HTTP 传输的文件对象">
          📦 导出对象
        </button>
        <button
          className="btn"
          onClick={() => api.downloadPcap({ file: pcapFile, filter: appliedFilter || '' })}
          disabled={!pcapFile}
          title={appliedFilter ? `下载过滤后的包（${appliedFilter}）` : '下载当前 pcap 文件'}
        >
          ⬇ 下载{appliedFilter ? '（已过滤）' : ''}
        </button>

        <select
          className="time-format-select"
          value={timeFormat}
          onChange={(e) => onTimeFormatChange(e.target.value)}
          title="时间列显示格式"
          disabled={!pcapFile}
        >
          <option value="relative">⏱ 相对时间</option>
          <option value="absolute">🕐 绝对时间</option>
          <option value="delta">Δ 间隔时间</option>
        </select>

        <div className="filter-box">
          <div className="filter-input-wrap">
            <input
              ref={filterInputRef}
              className={`filter-input ${filterValid === false ? 'filter-invalid' : filterValid === true && filter ? 'filter-valid' : ''}`}
              placeholder="显示过滤器，如 http.response.code >= 400（回车应用，/ 聚焦，Tab 补全）"
              value={filter}
              onChange={(e) => handleFilterInput(e.target.value)}
              onKeyDown={onFilterKeyDown}
              onFocus={() => { if (!filter && getHistory().length) setShowHistory(true) }}
              onBlur={() => setTimeout(() => { setCompletions([]); setShowHistory(false) }, 200)}
            />
            {filterValid === false && <span className="filter-badge filter-badge-err" title={filterMsg}>✕</span>}
            {filterValid === true && filter && <span className="filter-badge filter-badge-ok">✓</span>}

            {completions.length > 0 && (
              <div className="filter-dropdown">
                {completions.map((c, i) => (
                  <div
                    key={c.field}
                    className={`filter-dropdown-item ${i === compIndex ? 'filter-dropdown-active' : ''}`}
                    onMouseDown={(e) => { e.preventDefault(); applyCompletion(c.field) }}
                    onMouseEnter={() => setCompIndex(i)}
                  >
                    <span className="filter-field">{c.field}</span>
                    <span className="filter-desc">{c.desc}</span>
                  </div>
                ))}
              </div>
            )}

            {showHistory && getHistory().length > 0 && (
              <div className="filter-dropdown">
                <div className="filter-dropdown-header">历史过滤器</div>
                {getHistory().map((h, i) => (
                  <div
                    key={i}
                    className="filter-dropdown-item"
                    onMouseDown={(e) => { e.preventDefault(); onFilterChange(h); setShowHistory(false) }}
                  >
                    <span className="filter-field filter-history-item">{h}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
          <button className="btn btn-apply" onClick={doApply} disabled={!pcapFile || loading || filterValid === false}>应用</button>
          <button className="btn" onClick={() => handleFilterInput('')} title="清空过滤框">✕</button>
        </div>

        <span className="current-file" title={pcapFile}>
          {pcapFile ? pcapFile.split(/[\\/]/).pop() : '未打开文件'}
        </span>
      </div>

      {showFiles && (
        <div className="dropdown">
          <div className="dropdown-header">
            <span>历史抓包文件</span>
            <button className="btn btn-sm" onClick={refreshFiles}>刷新</button>
          </div>
          {files.length === 0 && <div className="dropdown-empty">暂无文件</div>}
          {files.map((f) => (
            <div key={f.path} className="dropdown-item" onClick={() => { onOpenFile(f.path); setShowFiles(false) }}>
              <span className="file-name">{f.filename}</span>
              <span className="file-meta">{f.size_kb} KB · {f.modified}</span>
            </div>
          ))}
        </div>
      )}

      {showCapture && (
        <div className="dropdown capture-dropdown">
          <div className="dropdown-header">
            <div className="capture-mode-tabs">
              <button
                className={`capture-mode-tab ${capMode === 'timed' ? 'capture-mode-active' : ''}`}
                onClick={() => setCapMode('timed')}
              >
                ⏱ 定时抓包
              </button>
              <button
                className={`capture-mode-tab ${capMode === 'live' ? 'capture-mode-active' : ''}`}
                onClick={() => setCapMode('live')}
              >
                🔴 实时瀑布流
              </button>
            </div>
            <button className="btn btn-sm" onClick={() => setShowCapture(false)}>关闭</button>
          </div>
          <div className="iface-list">
            {interfaces.map((i) => {
              const hist = currentTraffic(i)
              const active = capForm.interface === i.name
              return (
                <div
                  key={i.name}
                  className={`iface-item ${active ? 'iface-active' : ''}`}
                  onClick={() => setCapForm({ ...capForm, interface: i.name })}
                >
                  <div className="iface-info">
                    <div className="iface-name">{i.alias || i.name}</div>
                    <div className="iface-sub">
                      {i.traffic
                        ? `↓ ${formatBps(i.traffic.recv_bps)}  ↑ ${formatBps(i.traffic.sent_bps)}`
                        : '无流量数据'}
                    </div>
                  </div>
                  {hist && <TrafficSpark history={hist} />}
                </div>
              )
            })}
          </div>
          <div className="capture-form">
            <div className="capture-form-row">
              {capMode === 'timed' && (
                <>
                  <label>时长（秒）</label>
                  <input
                    type="number" min="1" max="300"
                    value={capForm.duration}
                    onChange={(e) => setCapForm({ ...capForm, duration: e.target.value })}
                  />
                </>
              )}
              <label>BPF 过滤器</label>
              <input
                type="text" placeholder="如 tcp port 80"
                value={capForm.bpf_filter}
                onChange={(e) => setCapForm({ ...capForm, bpf_filter: e.target.value })}
              />
            </div>
            {capMode === 'timed' ? (
              <>
                <button className="btn btn-primary" onClick={doCapture} disabled={capturing || !capForm.interface}>
                  {capturing ? `抓包中 ${Math.round((captureProgress || 0) * 100)}%` : '开始抓包（抓完自动打开）'}
                </button>
                {capturing && (
                  <div className="progress-track">
                    <div className="progress-fill" style={{ width: `${(captureProgress || 0) * 100}%` }} />
                  </div>
                )}
              </>
            ) : (
              <button
                className="btn btn-primary"
                onClick={() => { onStartLive(capForm.interface, capForm.bpf_filter); setShowCapture(false) }}
                disabled={!capForm.interface}
              >
                🔴 开始实时抓包（直接在主表格显示）
              </button>
            )}
            {captureMsg && <div className="capture-msg">{captureMsg}</div>}
          </div>
        </div>
      )}
    </div>
  )
}

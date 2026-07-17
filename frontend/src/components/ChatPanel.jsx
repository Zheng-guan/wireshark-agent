import React, { useState, useRef, useEffect } from 'react'
import { api } from '../api.js'

// AI 聊天控制台：语义过滤 + 对话。AI 总结改为通过 onSummarize 回调
// 触发独立的美观展示面板（不再混在聊天记录里）。
export default function ChatPanel({ pcapFile, currentFilter, onApplyFilter, checkedPackets, onSummarize }) {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: '你好！我是 Wireshark 智能助手 🦈\n\n你可以：\n• 用自然语言让我过滤流量，如「过滤出所有 HTTP 错误的包」\n• 勾选左侧数据包后点「AI 总结选中包」\n• 直接问我网络分析相关问题',
    },
  ])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [summarizing, setSummarizing] = useState(false)
  const listRef = useRef(null)

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages])

  const pushMessage = (role, content) =>
    setMessages((prev) => [...prev, { role, content }])

  const send = async () => {
    const text = input.trim()
    if (!text || sending) return
    setInput('')
    pushMessage('user', text)
    setSending(true)
    try {
      const resp = await api.chat({
        message: text,
        pcap_file: pcapFile,
        current_filter: currentFilter,
      })
      if (resp.intent === 'filter' && resp.filter) {
        pushMessage('assistant', `${resp.reply}\n\n过滤器：\`${resp.filter}\`\n\n已自动应用到列表。`)
        onApplyFilter(resp.filter)
      } else {
        pushMessage('assistant', resp.reply)
      }
    } catch (e) {
      pushMessage('assistant', `出错了：${e.message}`)
    } finally {
      setSending(false)
    }
  }

  const summarizeChecked = async () => {
    if (!checkedPackets.length || summarizing) return
    setSummarizing(true)
    try {
      const resp = await api.summarize(checkedPackets)
      // 触发独立面板展示，而不是塞进聊天记录
      onSummarize(resp.summary)
    } catch (e) {
      pushMessage('assistant', `总结失败：${e.message}`)
    } finally {
      setSummarizing(false)
    }
  }

  const onKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  return (
    <div className="chat-panel">
      <div className="chat-header">
        <span>🤖 AI 控制台</span>
        <button
          className="btn btn-sm btn-accent"
          disabled={!checkedPackets.length || summarizing}
          onClick={summarizeChecked}
          title={checkedPackets.length ? `总结选中的 ${checkedPackets.length} 个包` : '先在左侧勾选数据包'}
        >
          {summarizing ? '总结中…' : `✨ AI 总结 (${checkedPackets.length})`}
        </button>
      </div>

      <div className="chat-messages" ref={listRef}>
        {messages.map((m, i) => (
          <div key={i} className={`chat-msg chat-${m.role}`}>
            <div className="chat-bubble">{m.content}</div>
          </div>
        ))}
        {sending && (
          <div className="chat-msg chat-assistant">
            <div className="chat-bubble chat-thinking">思考中…</div>
          </div>
        )}
      </div>

      <div className="chat-input-box">
        <textarea
          className="chat-input"
          placeholder="例如：过滤出所有 HTTP 500 的包 / 这些包在干什么？"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          rows={2}
        />
        <button className="btn btn-primary chat-send" onClick={send} disabled={sending || !input.trim()}>
          发送
        </button>
      </div>
    </div>
  )
}

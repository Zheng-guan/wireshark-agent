import React, { useEffect, useRef, useState, useCallback } from 'react'

// 通用右键上下文菜单。
// 用法：
//   const { menu, openMenu, closeMenu } = useContextMenu()
//   <tr onContextMenu={(e) => openMenu(e, [...items])}>...
//   {menu}
// items: [{ label, icon?, danger?, disabled?, onClick }] 或 { divider: true }
export function useContextMenu() {
  const [state, setState] = useState(null) // {x, y, items}

  const openMenu = useCallback((e, items) => {
    e.preventDefault()
    e.stopPropagation()
    // 防止菜单超出视口
    const W = 220
    const H = items.length * 32 + 12
    const x = Math.min(e.clientX, window.innerWidth - W - 8)
    const y = Math.min(e.clientY, window.innerHeight - H - 8)
    setState({ x, y, items })
  }, [])

  const closeMenu = useCallback(() => setState(null), [])

  const menu = state ? (
    <ContextMenu x={state.x} y={state.y} items={state.items} onClose={closeMenu} />
  ) : null

  return { menu, openMenu, closeMenu }
}

export default function ContextMenu({ x, y, items, onClose }) {
  const ref = useRef(null)

  useEffect(() => {
    const onDown = (e) => {
      if (ref.current && !ref.current.contains(e.target)) onClose()
    }
    const onKey = (e) => { if (e.key === 'Escape') onClose() }
    const onScroll = () => onClose()
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    document.addEventListener('scroll', onScroll, true)
    window.addEventListener('blur', onClose)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
      document.removeEventListener('scroll', onScroll, true)
      window.removeEventListener('blur', onClose)
    }
  }, [onClose])

  return (
    <div ref={ref} className="context-menu" style={{ left: x, top: y }}>
      {items.map((item, i) =>
        item.divider ? (
          <div key={i} className="context-menu-divider" />
        ) : (
          <button
            key={i}
            className={`context-menu-item ${item.danger ? 'context-menu-danger' : ''}`}
            disabled={item.disabled}
            onClick={() => { onClose(); item.onClick?.() }}
          >
            {item.icon && <span className="context-menu-icon">{item.icon}</span>}
            <span>{item.label}</span>
            {item.hint && <span className="context-menu-hint">{item.hint}</span>}
          </button>
        ),
      )}
    </div>
  )
}

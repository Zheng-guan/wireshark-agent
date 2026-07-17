import React, { useRef, useCallback, useEffect } from 'react'

// 可拖拽分隔条：direction='row' 调整宽度（左右分栏），'column' 调整高度（上下分栏）
export default function Splitter({ direction = 'row', onDrag }) {
  const dragging = useRef(false)

  const onMouseDown = useCallback((e) => {
    dragging.current = true
    e.preventDefault()
    document.body.style.cursor = direction === 'row' ? 'col-resize' : 'row-resize'
    document.body.style.userSelect = 'none'
  }, [direction])

  useEffect(() => {
    const onMouseMove = (e) => {
      if (!dragging.current) return
      onDrag(direction === 'row' ? e.clientX : e.clientY)
    }
    const onMouseUp = () => {
      dragging.current = false
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }
    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)
    return () => {
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', onMouseUp)
    }
  }, [direction, onDrag])

  return (
    <div
      className={`splitter splitter-${direction}`}
      onMouseDown={onMouseDown}
      role="separator"
      aria-orientation={direction === 'row' ? 'vertical' : 'horizontal'}
    />
  )
}

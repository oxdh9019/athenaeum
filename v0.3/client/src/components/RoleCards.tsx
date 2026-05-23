/**
 * RoleCards.tsx — V0.7 角色卡片横向滚动区
 * 水平滚动容器，包含多张 AgentCard
 */

import { useRef, useState } from 'react'
import type { Agent } from '../context/WorldContext'
import AgentCard from './AgentCard'

interface RoleCardsProps {
  agents: Agent[]
  selectedAgent: string | null
  onSelectAgent: (id: string) => void
  onDiaryClick?: (agentId: string) => void
  style?: React.CSSProperties
}

const CARD_WIDTH = 300
const CARD_GAP = 12

function RoleCards({ agents, selectedAgent, onSelectAgent, onDiaryClick, style }: RoleCardsProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [showLeftArrow, setShowLeftArrow] = useState(false)
  const [showRightArrow, setShowRightArrow] = useState(false)

  const checkArrows = () => {
    const el = containerRef.current
    if (!el) return
    setShowLeftArrow(el.scrollLeft > 0)
    setShowRightArrow(el.scrollLeft < el.scrollWidth - el.clientWidth - 5)
  }

  const scrollTo = (direction: 'left' | 'right') => {
    const el = containerRef.current
    if (!el) return
    const scrollAmount = CARD_WIDTH + CARD_GAP
    el.scrollBy({
      left: direction === 'left' ? -scrollAmount : scrollAmount,
      behavior: 'smooth',
    })
    setTimeout(checkArrows, 300)
  }

  return (
    <div style={{
      height: '100%',
      background: '#1a1a2e',
      display: 'flex',
      alignItems: 'flex-start',
      flexShrink: 0,
      position: 'relative',
      overflow: 'hidden',
      ...style,
    }}>
      {/* 左箭头 */}
      {showLeftArrow && (
        <button
          onClick={() => scrollTo('left')}
          style={{
            position: 'absolute',
            left: '8px',
            top: '50%',
            transform: 'translateY(-50%)',
            zIndex: 10,
            width: '32px',
            height: '32px',
            borderRadius: '50%',
            border: 'none',
            background: '#2a2a4e',
            color: '#888',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '16px',
          }}
        >
          ‹
        </button>
      )}

      {/* 卡片滚动区 */}
      <div
        ref={containerRef}
        onScroll={checkArrows}
        style={{
          display: 'flex',
          gap: `${CARD_GAP}px`,
          padding: '12px 16px',
          overflowX: 'auto',
          overflowY: 'auto',
          scrollSnapType: 'x mandatory',
          scrollBehavior: 'smooth',
          height: '100%',
          width: '100%',
          alignItems: 'flex-start',
        }}
      >
        {agents.map((agent) => (
          <div key={agent.id} style={{ scrollSnapAlign: 'start' }}>
            <AgentCard
              agent={agent}
              selected={selectedAgent === agent.id}
              onClick={() => onSelectAgent(agent.id)}
              onDiaryClick={() => onDiaryClick?.(agent.id)}
            />
          </div>
        ))}
        {agents.length === 0 && (
          <div style={{ color: '#555', fontSize: '13px', padding: '20px' }}>
            暂无角色
          </div>
        )}
      </div>

      {/* 右箭头 */}
      {showRightArrow && (
        <button
          onClick={() => scrollTo('right')}
          style={{
            position: 'absolute',
            right: '8px',
            top: '50%',
            transform: 'translateY(-50%)',
            zIndex: 10,
            width: '32px',
            height: '32px',
            borderRadius: '50%',
            border: 'none',
            background: '#2a2a4e',
            color: '#888',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '16px',
          }}
        >
          ›
        </button>
      )}
    </div>
  )
}

export default RoleCards
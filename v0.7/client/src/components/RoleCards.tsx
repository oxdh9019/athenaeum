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
    <div
      className="role-cards-container"
      style={style}
    >
      {/* 左箭头 */}
      {showLeftArrow && (
        <button
          className="scroll-arrow left"
          onClick={() => scrollTo('left')}
        >
          ‹
        </button>
      )}

      {/* 卡片滚动区 */}
      <div
        ref={containerRef}
        className="role-cards-scroll"
        onScroll={checkArrows}
      >
        {(agents ?? []).map((agent) => (
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
          <div style={{ color: 'var(--text-muted)', fontSize: '13px', padding: '20px' }}>
            暂无角色
          </div>
        )}
      </div>

      {/* 右箭头 */}
      {showRightArrow && (
        <button
          className="scroll-arrow right"
          onClick={() => scrollTo('right')}
        >
          ›
        </button>
      )}
    </div>
  )
}

export default RoleCards
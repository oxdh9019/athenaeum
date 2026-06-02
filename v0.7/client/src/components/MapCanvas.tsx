/**
 * MapCanvas.tsx — V0.7 地图可视化组件
 * SVG 地图显示地点和角色位置
 */

import { useMemo } from 'react'
import type { Agent, Location } from '../context/WorldContext'

interface MapCanvasProps {
  agents: Agent[]
  locations: Location[]
  onAgentClick?: (agentId: string) => void
}

// 地点位置预设（基于 locations 数量动态布局）
const getLocationPosition = (index: number, total: number) => {
  const cols = Math.ceil(Math.sqrt(total))
  const cellWidth = 200
  const cellHeight = 150
  const startX = 40
  const startY = 40

  const col = index % cols
  const row = Math.floor(index / cols)

  return {
    x: startX + col * cellWidth,
    y: startY + row * cellHeight,
  }
}

const LOCATION_ICONS: Record<string, string> = {
  home: '🏠',
  tavern: '🍺',
  market: '🏪',
  square: '⛲',
  forest: '🌲',
  river: '🌊',
  mountain: '⛰️',
  temple: '⛩️',
  school: '🏫',
  default: '📍',
}

function getLocationIcon(tags: string[] = []): string {
  for (const tag of tags) {
    const lower = tag.toLowerCase()
    if (LOCATION_ICONS[lower]) return LOCATION_ICONS[lower]
  }
  return LOCATION_ICONS.default
}

const AGENT_COLORS = [
  'var(--accent-cyan)', 'var(--accent-yellow)', 'var(--accent-green)', 'var(--accent-purple)', 'var(--accent-red)',
  'var(--accent-blue)', '#ec4899', '#14b8a6', '#f97316', '#8b5cf6',
]

function MapCanvas({ agents = [], locations = [], onAgentClick }: MapCanvasProps) {
  const agentLocationMap = useMemo(() => {
    const map = new Map<string, Agent[]>()
    for (const agent of (agents ?? [])) {
      const existing = map.get(agent.location) || []
      existing.push(agent)
      map.set(agent.location, existing)
    }
    return map
  }, [agents])

  const safeLocations = Array.isArray(locations) ? locations : []
  const safeAgents = Array.isArray(agents) ? agents : []

  return (
    <div className="map-view" style={{
      background: 'var(--bg-secondary)',
      borderRadius: 'var(--border-radius)',
      padding: '16px',
      height: '100%',
      overflow: 'auto',
    }}>
      <h3 style={{ fontSize: '14px', color: 'var(--accent-cyan)', margin: '0 0 12px 0' }}>🗺️ 世界地图</h3>

      <svg
        width="100%"
        height="100%"
        viewBox="0 0 800 400"
        style={{ minHeight: '300px' }}
      >
        {/* 背景网格 */}
        <defs>
          <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
            <path d="M 40 0 L 0 0 0 40" fill="none" stroke="var(--border-default)" strokeWidth="0.5" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#grid)" />

        {/* 绘制地点 */}
        {safeLocations.map((loc, idx) => {
          const pos = getLocationPosition(idx, safeLocations.length)
          const agentsHere = agentLocationMap.get(loc.id) || []

          return (
            <g key={loc.id} transform={`translate(${pos.x}, ${pos.y})`}>
              {/* 地点背景 */}
              <rect
                x="0"
                y="0"
                width="160"
                height="100"
                rx="8"
                fill="var(--bg-tertiary)"
                stroke="var(--border-default)"
                strokeWidth="2"
              />

              {/* 地点名称 */}
              <text x="80" y="24" textAnchor="middle" fill="var(--text-primary)" fontSize="14" fontWeight="bold">
                {getLocationIcon(loc.tags || [])} {loc.name}
              </text>

              {/* 角色标记 */}
              {agentsHere.map((agent, aIdx) => (
                <g
                  key={agent.id}
                  transform={`translate(${20 + aIdx * 30}, 55)`}
                  style={{ cursor: 'pointer' }}
                  onClick={() => onAgentClick?.(agent.id)}
                >
                  <circle
                    cx="12"
                    cy="12"
                    r="12"
                    fill={AGENT_COLORS[safeAgents.indexOf(agent) % AGENT_COLORS.length]}
                  />
                  <text
                    x="12"
                    y="16"
                    textAnchor="middle"
                    fill="#000"
                    fontSize="10"
                    fontWeight="bold"
                  >
                    {agent.name?.[0] || '?'}
                  </text>
                  {/* 对话中指示 */}
                  {agent.is_active && (
                    <circle cx="22" cy="4" r="4" fill="var(--accent-green)" />
                  )}
                </g>
              ))}

              {/* 角色名称列表 */}
              {agentsHere.length > 0 && (
                <text x="80" y="88" textAnchor="middle" fill="var(--text-secondary)" fontSize="10">
                  {agentsHere.map(a => a.name).join(', ')}
                </text>
              )}
            </g>
          )
        })}
      </svg>

      {/* 图例 */}
      <div style={{ display: 'flex', gap: '16px', marginTop: '12px', fontSize: '11px', color: 'var(--text-muted)' }}>
        <span>● 在线对话</span>
        <span>○ 空闲</span>
      </div>
    </div>
  )
}

export default MapCanvas
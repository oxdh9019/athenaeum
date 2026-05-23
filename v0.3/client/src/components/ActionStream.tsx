/**
 * ActionStream.tsx — V0.7 互动舞台
 * 对话/动作统一流，垂直滚动，自动滚动到最新
 */

import { useEffect, useRef } from 'react'

interface StreamEntry {
  id: string
  type: 'dialogue' | 'action' | 'narrative'
  agentName?: string
  agentId?: string
  content: string
  tick: number
  emotion?: string
}

interface ActionStreamProps {
  entries: StreamEntry[]
  style?: React.CSSProperties
}

const AGENT_COLORS = [
  '#00d4ff', '#f59e0b', '#4ade80', '#a78bfa', '#ef4444',
]

function ActionStream({ entries, style }: ActionStreamProps) {
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [entries.length])

  const getAgentColor = (agentId: string) => {
    const hash = agentId.split('').reduce((acc, c) => acc + c.charCodeAt(0), 0)
    return AGENT_COLORS[hash % AGENT_COLORS.length]
  }

  return (
    <div
      style={{
        flex: 1,
        background: '#1a1a2e',
        borderRadius: '12px',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        ...style,
      }}
    >
      {/* 标题 */}
      <div style={{
        padding: '12px 16px',
        borderBottom: '1px solid #2a2a4e',
        flexShrink: 0,
      }}>
        <h3 style={{ fontSize: '14px', color: '#00d4ff', margin: 0 }}>
          🎭 互动舞台
        </h3>
      </div>

      {/* 内容区 */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        padding: '12px 16px',
        display: 'flex',
        flexDirection: 'column',
        gap: '8px',
      }}>
        {entries.length === 0 && (
          <div style={{ color: '#555', textAlign: 'center', padding: '40px', fontSize: '13px' }}>
            暂无互动内容...
          </div>
        )}
        {entries.map((entry, idx) => {
          const agentColor = entry.agentId ? getAgentColor(entry.agentId) : '#00d4ff'

          return (
            <div
              key={entry.id || idx}
              style={{
                display: 'flex',
                gap: '10px',
                alignItems: 'flex-start',
                background: entry.type === 'narrative' ? '#2a2a4e' : '#1a1a2e',
                borderRadius: '8px',
                padding: '10px 12px',
                border: entry.type === 'narrative' ? '1px solid #f59e0b40' : '1px solid #2a2a4e',
              }}
            >
              {/* 头像/Timeline */}
              {entry.type === 'dialogue' && entry.agentName && (
                <div style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: '50%',
                  background: agentColor + '40',
                  border: `2px solid ${agentColor}`,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '12px',
                  fontWeight: 'bold',
                  color: agentColor,
                  flexShrink: 0,
                }}>
                  {entry.agentName[0]}
                </div>
              )}
              {entry.type === 'action' && (
                <div style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: '50%',
                  background: '#3a3a5e',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '14px',
                  flexShrink: 0,
                }}>
                  {entry.content[0] || '•'}
                </div>
              )}
              {entry.type === 'narrative' && (
                <div style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: '50%',
                  background: '#f59e0b20',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '14px',
                  flexShrink: 0,
                }}>
                  🔥
                </div>
              )}

              {/* 内容 */}
              <div style={{ flex: 1, minWidth: 0 }}>
                {/* 头部：名字 + Tick */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                  {entry.agentName && (
                    <span style={{ fontSize: '13px', fontWeight: 'bold', color: agentColor }}>
                      {entry.agentName}
                    </span>
                  )}
                  {entry.type === 'narrative' && (
                    <span style={{ fontSize: '11px', color: '#f59e0b', background: '#f59e0b20', padding: '2px 6px', borderRadius: '4px' }}>
                      叙事事件
                    </span>
                  )}
                  <span style={{ fontSize: '11px', color: '#444' }}>
                    #{entry.tick}
                  </span>
                </div>

                {/* 内容文字 */}
                <div style={{
                  fontSize: entry.type === 'narrative' ? '13px' : '14px',
                  color: entry.type === 'narrative' ? '#f59e0b' : '#e0e0e0',
                  lineHeight: 1.5,
                }}>
                  {entry.content}
                </div>

                {/* 情感标签 */}
                {entry.emotion && entry.type !== 'narrative' && (
                  <div style={{ fontSize: '11px', color: '#666', marginTop: '4px' }}>
                    💬 {entry.emotion}
                  </div>
                )}
              </div>
            </div>
          )
        })}
        <div ref={endRef} />
      </div>
    </div>
  )
}

export default ActionStream
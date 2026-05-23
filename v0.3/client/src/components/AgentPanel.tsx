/**
 * AgentPanel.tsx — V0.7 角色状态面板
 * 显示角色详细信息、情绪、需求
 */

import type { Agent } from '../context/WorldContext'

interface AgentPanelProps {
  agents: Agent[]
  selectedAgent: string | null
  onSelectAgent: (id: string) => void
  viewMode: 'observe' | 'possess'
  onPossessClick?: (agentId: string) => void
}

const MOOD_ICONS: Record<string, string> = {
  happy: '😊',
  sad: '😢',
  angry: '😠',
  fearful: '😨',
  curious: '🤔',
  neutral: '😐',
  warm: '😊',
  anxious: '😟',
  wary: '😐',
}

function AgentPanel({ agents, selectedAgent, onSelectAgent, viewMode, onPossessClick }: AgentPanelProps) {
  return (
    <div style={{
      background: '#1a1a2e',
      borderRadius: '12px',
      padding: '16px',
      display: 'flex',
      flexDirection: 'column',
      gap: '12px',
      height: '100%',
      overflow: 'hidden',
    }}>
      <h3 style={{ fontSize: '14px', color: '#00d4ff', margin: 0 }}>👥 角色列表</h3>

      <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {agents.map((agent) => (
          <div
            key={agent.id}
            onClick={() => onSelectAgent(agent.id)}
            style={{
              background: selectedAgent === agent.id ? '#2a2a4e' : '#1a1a2e',
              borderRadius: '8px',
              padding: '10px',
              cursor: 'pointer',
              border: selectedAgent === agent.id ? '1px solid #00d4ff' : '1px solid #2a2a4e',
            }}
          >
            {/* 头部：名称 + 状态 */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <div style={{
                  width: '28px',
                  height: '28px',
                  borderRadius: '50%',
                  background: '#3a3a5e',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '12px',
                  color: '#00d4ff',
                }}>
                  {agent.name[0]}
                </div>
                <div>
                  <div style={{ fontSize: '13px', fontWeight: 'bold', color: '#e0e0e0' }}>{agent.name}</div>
                  <div style={{ fontSize: '10px', color: '#666' }}>@{agent.location}</div>
                </div>
              </div>
              {agent.is_active && (
                <span style={{ fontSize: '10px', color: '#4ade80', background: '#4ade8020', padding: '2px 6px', borderRadius: '8px' }}>
                  💬 对话中
                </span>
              )}
            </div>

            {/* 情绪 */}
            {agent.mood && (
              <div style={{ fontSize: '11px', color: '#f59e0b', marginBottom: '4px' }}>
                {MOOD_ICONS[agent.mood] || '😐'} 情绪: {agent.mood}
              </div>
            )}

            {/* 意图 */}
            {agent.intention && (
              <div style={{ fontSize: '11px', color: '#a78bfa', marginBottom: '4px' }}>
                🎯 {agent.intention}
              </div>
            )}

            {/* 附近角色 */}
            {agent.neighbors.length > 0 && (
              <div style={{ fontSize: '10px', color: '#666', marginBottom: '4px' }}>
                附近: {agent.neighbors.map(id => agents.find(a => a.id === id)?.name || id).join(', ')}
              </div>
            )}

            {/* 人格特质 */}
            {agent.personality && (
              <div style={{ display: 'flex', gap: '3px', flexWrap: 'wrap', fontSize: '9px' }}>
                {['O', 'C', 'E', 'A', 'N'].map((trait, i) => {
                  const values = ['openness', 'conscientiousness', 'extraversion', 'agreeableness', 'neuroticism']
                  const value = agent.personality![values[i] as keyof typeof agent.personality]
                  return (
                    <span
                      key={trait}
                      style={{
                        background: '#2a2a4e',
                        padding: '2px 4px',
                        borderRadius: '3px',
                        color: value > 0.6 ? '#4ade80' : value < 0.4 ? '#ef4444' : '#888',
                      }}
                    >
                      {trait}:{value.toFixed(1)}
                    </span>
                  )
                })}
              </div>
            )}

            {/* 附身按钮 */}
            {viewMode === 'possess' && (
              <button
                onClick={(e) => { e.stopPropagation(); onPossessClick?.(agent.id) }}
                style={{
                  width: '100%',
                  marginTop: '6px',
                  padding: '4px',
                  borderRadius: '4px',
                  border: 'none',
                  background: selectedAgent === agent.id ? '#4ade80' : '#3a3a5e',
                  color: '#fff',
                  cursor: 'pointer',
                  fontSize: '11px',
                }}
              >
                {selectedAgent === agent.id ? '✓ 已选择' : '选择附身'}
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

export default AgentPanel
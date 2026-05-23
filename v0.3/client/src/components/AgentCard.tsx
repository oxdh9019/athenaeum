/**
 * AgentCard.tsx — V0.7 单张角色卡片
 * 填满父容器高度，显示角色详细信息
 */

import type { Agent } from '../context/WorldContext'

interface AgentCardProps {
  agent: Agent
  selected?: boolean
  onClick?: () => void
  onDiaryClick?: () => void
}

const MOOD_ICONS: Record<string, string> = {
  happy: '😊', sad: '😢', angry: '😠', fearful: '😨',
  curious: '🤔', neutral: '😐', warm: '😊', anxious: '😟', wary: '😐',
}

function AgentCard({ agent, selected, onClick, onDiaryClick }: AgentCardProps) {
  const traitKeys = ['openness', 'conscientiousness', 'extraversion', 'agreeableness', 'neuroticism']
  const traitLabels = ['O', 'C', 'E', 'A', 'N']

  return (
    <div
      onClick={onClick}
      style={{
        width: '300px',
        minHeight: '200px',
        height: '100%',
        background: selected ? '#2a2a4e' : '#1a1a2e',
        borderRadius: '12px',
        padding: '16px',
        border: selected ? '2px solid #00d4ff' : '1px solid #2a2a4e',
        cursor: 'pointer',
        display: 'flex',
        flexDirection: 'column',
        gap: '10px',
        flexShrink: 0,
        transition: 'border-color 0.2s',
        overflow: 'hidden',
      }}
    >
      {/* 头部：头像 + 名字 + 情绪 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <div style={{
          width: '48px',
          height: '48px',
          borderRadius: '50%',
          background: '#3a3a5e',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: '20px',
          color: '#00d4ff',
          flexShrink: 0,
          border: agent.is_active ? '2px solid #4ade80' : 'none',
        }}>
          {agent.name[0]}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '15px', fontWeight: 'bold', color: '#e0e0e0' }}>{agent.name}</span>
            {agent.is_active && (
              <span style={{
                fontSize: '10px',
                background: '#4ade80',
                color: '#000',
                padding: '1px 6px',
                borderRadius: '8px',
                fontWeight: 'bold',
              }}>
                对话中
              </span>
            )}
          </div>
          <div style={{ fontSize: '12px', color: '#666', marginTop: '2px' }}>
            📍 {agent.location}
          </div>
        </div>
        {agent.mood && (
          <div style={{ fontSize: '20px' }}>
            {MOOD_ICONS[agent.mood] || '😐'}
          </div>
        )}
      </div>

      {/* 情绪文字 */}
      {agent.mood && (
        <div style={{ fontSize: '12px', color: '#888' }}>
          情绪：{agent.mood}
        </div>
      )}

      {/* 人格五因子标签 */}
      {agent.personality && (
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
          {traitLabels.map((label, i) => {
            const value = agent.personality![traitKeys[i] as keyof typeof agent.personality] as number
            const color = value > 0.6 ? '#4ade80' : value < 0.4 ? '#ef4444' : '#666'
            return (
              <span
                key={label}
                style={{
                  padding: '3px 8px',
                  borderRadius: '4px',
                  fontSize: '11px',
                  background: '#2a2a4e',
                  color: color,
                  fontWeight: 'bold',
                }}
              >
                {label}: {(value * 10).toFixed(0)}
              </span>
            )
          })}
        </div>
      )}

      {/* 需求进度条 */}
      {agent.desires && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <div style={{ fontSize: '11px', color: '#666' }}>❤️ 需求</div>
          {(['safety', 'belonging', 'novelty'] as const).map((need, idx) => {
            const labels = { safety: '🛡️ 安全', belonging: '❤️ 归属', novelty: '✨ 新奇' }
            const colors = { safety: '#4ade80', belonging: '#f59e0b', novelty: '#00d4ff' }
            return (
              <div key={need} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '10px', color: '#888', width: '40px' }}>{labels[need]}</span>
                <div style={{ flex: 1, height: '6px', background: '#2a2a4e', borderRadius: '3px' }}>
                  <div
                    style={{
                      width: `${(agent.desires![need] || 0) * 100}%`,
                      height: '100%',
                      background: colors[need],
                      borderRadius: '3px',
                    }}
                  />
                </div>
                <span style={{ fontSize: '10px', color: '#666', width: '30px', textAlign: 'right' }}>
                  {(agent.desires![need] * 100).toFixed(0)}%
                </span>
              </div>
            )
          })}
        </div>
      )}

      {/* 当前意图 */}
      {agent.intention && (
        <div style={{
          fontSize: '12px',
          color: '#a78bfa',
          background: '#2a2a4e',
          padding: '6px 10px',
          borderRadius: '6px',
        }}>
          🎯 {agent.intention}
        </div>
      )}

      {/* 附近角色 */}
      {agent.neighbors.length > 0 && (
        <div style={{ fontSize: '11px', color: '#666' }}>
          附近：{agent.neighbors.slice(0, 3).join(', ')}
          {agent.neighbors.length > 3 && ` +${agent.neighbors.length - 3}`}
        </div>
      )}

      {/* 底部：日记按钮 */}
      <div style={{ marginTop: 'auto', display: 'flex', justifyContent: 'flex-end' }}>
        <button
          onClick={(e) => { e.stopPropagation(); onDiaryClick?.() }}
          style={{
            padding: '6px 12px',
            borderRadius: '6px',
            border: 'none',
            background: '#3a3a5e',
            color: '#888',
            cursor: 'pointer',
            fontSize: '12px',
          }}
        >
          📔 日记
        </button>
      </div>
    </div>
  )
}

export default AgentCard
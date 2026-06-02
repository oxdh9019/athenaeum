/**
 * AgentCard.tsx — V0.7 单张角色卡片
 * 显示角色详细信息，支持选中状态
 */

import type { Agent } from '../context/WorldContext'

interface AgentCardProps {
  agent: Agent
  selected?: boolean
  onClick?: () => void
  onDiaryClick?: () => void
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

function AgentCard({ agent, selected, onClick, onDiaryClick }: AgentCardProps) {
  const traitKeys = ['openness', 'conscientiousness', 'extraversion', 'agreeableness', 'neuroticism']
  const traitLabels = ['O', 'C', 'E', 'A', 'N']

  return (
    <div
      onClick={onClick}
      className={`agent-card ${selected ? 'selected' : ''}`}
      style={{
        width: '300px',
        minHeight: '200px',
        height: '100%',
        background: selected ? 'var(--bg-tertiary)' : 'var(--bg-secondary)',
        borderRadius: 'var(--border-radius)',
        padding: '16px',
        border: selected ? '2px solid var(--accent-cyan)' : '1px solid var(--border-default)',
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
          background: 'var(--bg-tertiary)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: '20px',
          color: 'var(--accent-cyan)',
          flexShrink: 0,
          border: agent.is_active ? '2px solid var(--accent-green)' : 'none',
        }}>
          {agent.name[0]}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '15px', fontWeight: 'bold', color: 'var(--text-primary)' }}>{agent.name}</span>
            {agent.is_active && (
              <span style={{
                fontSize: '10px',
                background: 'var(--accent-green)',
                color: '#000',
                padding: '1px 6px',
                borderRadius: '8px',
                fontWeight: 'bold',
              }}>
                对话中
              </span>
            )}
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '2px' }}>
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
      {agent.emotion_state && (
        <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
          情绪：{agent.emotion_state.label} (效价: {agent.emotion_state.valence?.toFixed(2)}, 唤醒: {agent.emotion_state.arousal?.toFixed(2)})
        </div>
      )}

      {/* 人格五因子标签 */}
      {agent.personality && (
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
          {traitLabels.map((label, i) => {
            const value = agent.personality![traitKeys[i] as keyof typeof agent.personality] as number
            const color = value > 0.6 ? 'var(--accent-green)' : value < 0.4 ? 'var(--accent-red)' : 'var(--text-muted)'
            return (
              <span
                key={label}
                style={{
                  padding: '3px 8px',
                  borderRadius: '4px',
                  fontSize: '11px',
                  background: 'var(--bg-tertiary)',
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

      {/* 需求进度条 (V0.7 Soul Core Desires) */}
      {agent.soul?.core_desires && agent.soul.core_desires.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>❤️ 核心欲望</div>
          {agent.soul.core_desires.map((desire, idx) => (
            <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '10px', color: 'var(--text-secondary)', width: '60px' }}>{desire.name}</span>
              <div style={{ flex: 1, height: '6px', background: 'var(--bg-tertiary)', borderRadius: '3px' }}>
                <div
                  style={{
                    width: `${desire.level * 100}%`,
                    height: '100%',
                    background: idx === 0 ? 'var(--accent-blue)' : idx === 1 ? 'var(--accent-purple)' : 'var(--accent-cyan)',
                    borderRadius: '3px',
                  }}
                />
              </div>
              <span style={{ fontSize: '10px', color: 'var(--text-muted)', width: '30px', textAlign: 'right' }}>
                {(desire.level * 100).toFixed(0)}%
              </span>
            </div>
          ))}
        </div>
      )}

      {/* 当前意图 */}
      {agent.intention && (
        <div style={{
          fontSize: '12px',
          color: 'var(--accent-purple)',
          background: 'var(--bg-tertiary)',
          padding: '6px 10px',
          borderRadius: 'var(--border-radius-sm)',
        }}>
          🎯 {agent.intention}
        </div>
      )}

      {/* 当前目标 */}
      {agent.active_goal && (
        <div style={{
          fontSize: '12px',
          color: 'var(--accent-yellow)',
          background: 'rgba(245, 158, 11, 0.13)',
          padding: '6px 10px',
          borderRadius: 'var(--border-radius-sm)',
        }}>
          🎯 当前目标: {typeof agent.active_goal === 'string' ? agent.active_goal : (agent.active_goal?.description ?? '')}
        </div>
      )}

      {/* 附近角色 */}
      {(agent.neighbors?.length ?? 0) > 0 && (
        <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
          附近：{agent.neighbors!.slice(0, 3).join(', ')}
          {(agent.neighbors?.length ?? 0) > 3 && ` +${(agent.neighbors!.length - 3)}`}
        </div>
      )}

      {/* 底部：日记按钮 */}
      <div style={{ marginTop: 'auto', display: 'flex', justifyContent: 'flex-end' }}>
        <button
          onClick={(e) => { e.stopPropagation(); onDiaryClick?.() }}
          style={{
            padding: '6px 12px',
            borderRadius: 'var(--border-radius-sm)',
            border: 'none',
            background: 'var(--bg-tertiary)',
            color: 'var(--text-secondary)',
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
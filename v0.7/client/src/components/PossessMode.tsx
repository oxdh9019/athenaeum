/**
 * PossessMode.tsx — V0.7 附身模式组件
 * 用户接管角色后的聊天界面
 */

import { useEffect, useRef, useState } from 'react'
import type { Agent } from '../context/WorldContext'

export interface PossessTurn {
  role: 'user' | 'agent'
  text: string
  ts: number
}

interface PossessModeProps {
  agent: Agent | null
  onSend: (message: string) => void
  onRelease: () => void
  turns: PossessTurn[]
  pending: boolean
}

function PossessMode({ agent, onSend, onRelease, turns, pending }: PossessModeProps) {
  const [message, setMessage] = useState('')
  const scrollRef = useRef<HTMLDivElement>(null)

  const handleSend = () => {
    if (!message.trim()) return
    onSend(message)
    setMessage('')
  }

  useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [turns.length, pending])

  if (!agent) {
    return (
      <div style={{
        background: 'var(--bg-secondary)',
        borderRadius: 'var(--border-radius)',
        padding: '16px',
        textAlign: 'center',
        color: 'var(--text-muted)',
        fontSize: '14px',
      }}>
        请先在左侧选择一个角色进行附身
      </div>
    )
  }

  return (
    <div style={{
      background: 'var(--bg-secondary)',
      borderRadius: 'var(--border-radius)',
      padding: '16px',
      display: 'flex',
      flexDirection: 'column',
      gap: '12px',
      height: '100%',
    }}>
      {/* 头部 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            width: '36px',
            height: '36px',
            borderRadius: '50%',
            background: 'var(--accent-green)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '16px',
          }}>
            {agent.name[0]}
          </div>
          <div>
            <div style={{ fontSize: '14px', fontWeight: 'bold', color: 'var(--accent-green)' }}>🎭 正在附身</div>
            <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>{agent.name}</div>
          </div>
        </div>
        <button
          onClick={onRelease}
          style={{
            padding: '8px 16px',
            borderRadius: 'var(--border-radius-sm)',
            border: 'none',
            background: 'var(--accent-red)',
            color: '#fff',
            cursor: 'pointer',
            fontSize: '12px',
            fontWeight: 'bold',
          }}
        >
          释放附身
        </button>
      </div>

      {/* 情绪状态 */}
      <div style={{
        background: 'var(--bg-tertiary)',
        borderRadius: 'var(--border-radius-sm)',
        padding: '10px',
        fontSize: '12px',
        color: 'var(--text-secondary)',
        display: 'flex',
        gap: '16px',
      }}>
        {agent.emotion_state && <span>情绪: {agent.emotion_state.label}</span>}
        {agent.intention && <span>🎯 意图: {agent.intention}</span>}
        <span>📍 {agent.location}</span>
      </div>

      {/* 输入区域 */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '8px', minHeight: 0 }}>
        <div
          ref={scrollRef}
          style={{
            flex: 1,
            overflowY: 'auto',
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
            padding: '8px',
            background: 'var(--bg-primary)',
            borderRadius: 'var(--border-radius-sm)',
            border: '1px solid var(--border-default)',
            minHeight: '120px',
            maxHeight: '320px',
          }}
        >
          {turns.length === 0 && !pending && (
            <div style={{ color: 'var(--text-muted)', fontSize: '12px', textAlign: 'center', margin: 'auto' }}>
              暂无对话。在下方输入框说话,按 Enter 发送。
            </div>
          )}
          {turns.map((t, i) => (
            <div
              key={i}
              style={{
                alignSelf: t.role === 'user' ? 'flex-end' : 'flex-start',
                maxWidth: '80%',
                padding: '8px 12px',
                borderRadius: 'var(--border-radius-sm)',
                background: t.role === 'user' ? 'var(--accent-cyan)' : 'var(--bg-tertiary)',
                color: t.role === 'user' ? '#000' : 'var(--text-primary)',
                fontSize: '13px',
                lineHeight: 1.5,
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
              }}
            >
              <div style={{ fontSize: '10px', opacity: 0.6, marginBottom: '2px' }}>
                {t.role === 'user' ? '你' : agent.name}
              </div>
              {t.text}
            </div>
          ))}
          {pending && (
            <div
              style={{
                alignSelf: 'flex-start',
                padding: '8px 12px',
                borderRadius: 'var(--border-radius-sm)',
                background: 'var(--bg-tertiary)',
                color: 'var(--text-muted)',
                fontSize: '12px',
                fontStyle: 'italic',
              }}
            >
              {agent.name} 正在输入…
            </div>
          )}
        </div>
        <textarea
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              handleSend()
            }
          }}
          placeholder="输入你要说的话... (Enter 发送, Shift+Enter 换行)"
          style={{
            flex: 1,
            padding: '12px',
            borderRadius: 'var(--border-radius-sm)',
            border: '1px solid var(--border-default)',
            background: 'var(--bg-primary)',
            color: 'var(--text-primary)',
            fontSize: '14px',
            resize: 'none',
            fontFamily: 'inherit',
          }}
        />
        <button
          onClick={handleSend}
          disabled={!message.trim()}
          style={{
            padding: '12px',
            borderRadius: 'var(--border-radius-sm)',
            border: 'none',
            background: message.trim() ? 'var(--accent-green)' : 'var(--bg-tertiary)',
            color: message.trim() ? '#000' : 'var(--text-muted)',
            cursor: message.trim() ? 'pointer' : 'not-allowed',
            fontSize: '14px',
            fontWeight: 'bold',
          }}
        >
          发送
        </button>
      </div>

      {/* 提示 */}
      <div style={{ fontSize: '11px', color: 'var(--text-muted)', textAlign: 'center' }}>
        附身时对话将使用云端模型以获得最佳表现力
      </div>
    </div>
  )
}

export default PossessMode
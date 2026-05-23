/**
 * PossessMode.tsx — V0.7 附身模式组件
 * 用户接管角色后的聊天界面
 */

import { useState } from 'react'
import type { Agent } from '../context/WorldContext'

interface PossessModeProps {
  agent: Agent | null
  onSend: (message: string) => void
  onRelease: () => void
}

function PossessMode({ agent, onSend, onRelease }: PossessModeProps) {
  const [message, setMessage] = useState('')

  const handleSend = () => {
    if (!message.trim()) return
    onSend(message)
    setMessage('')
  }

  if (!agent) {
    return (
      <div style={{
        background: '#1a1a2e',
        borderRadius: '12px',
        padding: '16px',
        textAlign: 'center',
        color: '#666',
        fontSize: '14px',
      }}>
        请先在左侧选择一个角色进行附身
      </div>
    )
  }

  return (
    <div style={{
      background: '#1a1a2e',
      borderRadius: '12px',
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
            background: '#4ade80',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '16px',
          }}>
            {agent.name[0]}
          </div>
          <div>
            <div style={{ fontSize: '14px', fontWeight: 'bold', color: '#4ade80' }}>🎭 正在附身</div>
            <div style={{ fontSize: '12px', color: '#888' }}>{agent.name}</div>
          </div>
        </div>
        <button
          onClick={onRelease}
          style={{
            padding: '8px 16px',
            borderRadius: '8px',
            border: 'none',
            background: '#ef4444',
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
        background: '#2a2a4e',
        borderRadius: '8px',
        padding: '10px',
        fontSize: '12px',
        color: '#888',
        display: 'flex',
        gap: '16px',
      }}>
        {agent.mood && <span>😊 情绪: {agent.mood}</span>}
        {agent.intention && <span>🎯 意图: {agent.intention}</span>}
      </div>

      {/* 输入区域 */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '8px' }}>
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
            borderRadius: '8px',
            border: '1px solid #3a3a5e',
            background: '#1a1a2e',
            color: '#e0e0e0',
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
            borderRadius: '8px',
            border: 'none',
            background: message.trim() ? '#4ade80' : '#333',
            color: message.trim() ? '#000' : '#666',
            cursor: message.trim() ? 'pointer' : 'not-allowed',
            fontSize: '14px',
            fontWeight: 'bold',
          }}
        >
          发送
        </button>
      </div>

      {/* 提示 */}
      <div style={{ fontSize: '11px', color: '#555', textAlign: 'center' }}>
        附身时对话将使用云端模型以获得最佳表现力
      </div>
    </div>
  )
}

export default PossessMode
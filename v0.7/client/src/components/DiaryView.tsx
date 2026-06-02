/**
 * DiaryView.tsx — V0.7 角色日记组件
 * 显示角色的长期记忆摘要
 */

import { useEffect, useState } from 'react'
import type { Agent } from '../context/WorldContext'

export interface Memory {
  memory_id: string
  content: string
  emotion: string
  importance: number
  tick_created: number
  is_core: boolean
  context: string
}

interface DiaryViewProps {
  agents: Agent[]
  selectedAgent: string
  onSelectAgent: (id: string) => void
}

function DiaryView({ agents, selectedAgent, onSelectAgent }: DiaryViewProps) {
  const [loading, setLoading] = useState(false)
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [internalMemories, setInternalMemories] = useState<Memory[]>([])
  const pageSize = 10

  useEffect(() => {
    if (!selectedAgent) return
    fetchDiary(selectedAgent, page)
  }, [selectedAgent, page])

  const fetchDiary = async (agentId: string, pageNum: number) => {
    setLoading(true)
    try {
      const resp = await fetch(`/agent/${agentId}/journal?page=${pageNum}&size=${pageSize}`)
      const data = await resp.json()
      setInternalMemories(data.memories || [])
      setTotal(data.total || 0)
    } catch (e) {
      console.error('获取日记失败:', e)
    }
    setLoading(false)
  }

  const emotionColor = (emotion: string) => {
    switch (emotion) {
      case 'warm': return 'var(--accent-yellow)'
      case 'curious': return 'var(--accent-blue)'
      case 'anxious': return 'var(--accent-red)'
      case 'wary': return 'var(--accent-purple)'
      default: return 'var(--text-secondary)'
    }
  }

  const emotionLabel = (emotion: string) => {
    switch (emotion) {
      case 'warm': return '温暖'
      case 'curious': return '好奇'
      case 'neutral': return '平静'
      case 'wary': return '谨慎'
      case 'anxious': return '焦虑'
      default: return emotion
    }
  }

  const totalPages = Math.ceil(total / pageSize)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: '12px' }}>
      {/* 角色选择 */}
      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', flexShrink: 0 }}>
        <span style={{ color: 'var(--text-secondary)', fontSize: '12px', lineHeight: '32px' }}>选择角色:</span>
        {agents.map(agent => (
          <button
            key={agent.id}
            onClick={() => { onSelectAgent(agent.id); setPage(1) }}
            style={{
              padding: '6px 12px',
              borderRadius: '16px',
              border: 'none',
              background: selectedAgent === agent.id ? 'var(--accent-cyan)' : 'var(--bg-tertiary)',
              color: selectedAgent === agent.id ? '#000' : '#fff',
              cursor: 'pointer',
              fontSize: '12px',
              fontWeight: 'bold',
            }}
          >
            {agent.name}
          </button>
        ))}
      </div>

      {/* 日记内容 */}
      <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {!selectedAgent && (
          <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '40px', fontSize: '14px' }}>
            请选择上方角色查看其日记
          </div>
        )}
        {selectedAgent && loading && (
          <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '40px', fontSize: '14px' }}>
            加载中...
          </div>
        )}
        {selectedAgent && !loading && internalMemories.length === 0 && (
          <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '40px', fontSize: '14px' }}>
            暂无记忆
          </div>
        )}
        {internalMemories.map((mem, idx) => (
          <div
            key={mem.memory_id || idx}
            style={{
              background: 'var(--bg-secondary)',
              borderRadius: 'var(--border-radius)',
              padding: '14px',
              border: mem.is_core ? '1px solid var(--accent-yellow)' : '1px solid var(--border-default)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <span
                  style={{
                    padding: '2px 8px',
                    borderRadius: '10px',
                    fontSize: '11px',
                    background: 'var(--bg-tertiary)',
                    color: emotionColor(mem.emotion),
                  }}
                >
                  {emotionLabel(mem.emotion)}
                </span>
                {mem.is_core && (
                  <span style={{ padding: '2px 8px', borderRadius: '10px', fontSize: '11px', background: 'var(--accent-yellow)', color: '#000' }}>
                    核心记忆
                  </span>
                )}
              </div>
              <div style={{ display: 'flex', gap: '12px', fontSize: '11px', color: 'var(--text-muted)' }}>
                <span>重要性: {mem.importance.toFixed(2)}</span>
                <span>Tick: {mem.tick_created}</span>
              </div>
            </div>
            <div style={{ fontSize: '14px', color: 'var(--text-primary)', lineHeight: '1.5', marginBottom: '8px' }}>
              {mem.content}
            </div>
            {mem.context && (
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                参与者: {mem.context}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* 分页 */}
      {selectedAgent && total > 0 && (
        <div style={{ display: 'flex', justifyContent: 'center', gap: '8px', flexShrink: 0 }}>
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page <= 1}
            style={{
              padding: '6px 12px',
              borderRadius: 'var(--border-radius-sm)',
              border: 'none',
              background: page <= 1 ? 'var(--bg-tertiary)' : 'var(--bg-card)',
              color: page <= 1 ? 'var(--text-muted)' : '#fff',
              cursor: page <= 1 ? 'not-allowed' : 'pointer',
            }}
          >
            上一页
          </button>
          <span style={{ color: 'var(--text-secondary)', fontSize: '12px', lineHeight: '32px' }}>
            第 {page} / {totalPages} 页，共 {total} 条
          </span>
          <button
            onClick={() => setPage(p => p + 1)}
            disabled={page >= totalPages}
            style={{
              padding: '6px 12px',
              borderRadius: 'var(--border-radius-sm)',
              border: 'none',
              background: page >= totalPages ? 'var(--bg-tertiary)' : 'var(--bg-card)',
              color: page >= totalPages ? 'var(--text-muted)' : '#fff',
              cursor: page >= totalPages ? 'not-allowed' : 'pointer',
            }}
          >
            下一页
          </button>
        </div>
      )}
    </div>
  )
}

export default DiaryView
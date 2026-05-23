/**
 * DiaryView.tsx — V0.5 角色日记组件
 * 显示角色的长期记忆摘要
 */

import { useEffect, useState } from 'react'

interface Memory {
  memory_id: string
  content: string
  emotion: string
  importance: number
  tick_created: number
  is_core: boolean
  context: string
}

interface Agent {
  id: string
  name: string
}

interface DiaryViewProps {
  agents: Agent[]
  selectedAgent: string
  onSelectAgent: (id: string) => void
  memories: Memory[]
  setMemories: (m: Memory[]) => void
}

function DiaryView({ agents, selectedAgent, onSelectAgent, memories, setMemories }: DiaryViewProps) {
  const [loading, setLoading] = useState(false)
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
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
      setMemories(data.memories || [])
      setTotal(data.total || 0)
    } catch (e) {
      console.error('获取日记失败:', e)
    }
    setLoading(false)
  }

  const emotionColor = (emotion: string) => {
    switch (emotion) {
      case 'warm': return '#f59e0b'
      case 'curious': return '#3b82f6'
      case 'anxious': return '#ef4444'
      case 'wary': return '#a78bfa'
      default: return '#888'
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
        <span style={{ color: '#888', fontSize: '12px', lineHeight: '32px' }}>选择角色:</span>
        {agents.map(agent => (
          <button
            key={agent.id}
            onClick={() => { onSelectAgent(agent.id); setPage(1) }}
            style={{
              padding: '6px 12px',
              borderRadius: '16px',
              border: 'none',
              background: selectedAgent === agent.id ? '#00d4ff' : '#2a2a4e',
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
          <div style={{ color: '#666', textAlign: 'center', padding: '40px', fontSize: '14px' }}>
            请选择上方角色查看其日记
          </div>
        )}
        {selectedAgent && loading && (
          <div style={{ color: '#666', textAlign: 'center', padding: '40px', fontSize: '14px' }}>
            加载中...
          </div>
        )}
        {selectedAgent && !loading && memories.length === 0 && (
          <div style={{ color: '#666', textAlign: 'center', padding: '40px', fontSize: '14px' }}>
            暂无记忆
          </div>
        )}
        {memories.map((mem, idx) => (
          <div
            key={mem.memory_id || idx}
            style={{
              background: '#1a1a2e',
              borderRadius: '12px',
              padding: '14px',
              border: mem.is_core ? '1px solid #f59e0b' : '1px solid #2a2a4e',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <span
                  style={{
                    padding: '2px 8px',
                    borderRadius: '10px',
                    fontSize: '11px',
                    background: '#2a2a4e',
                    color: emotionColor(mem.emotion),
                  }}
                >
                  {emotionLabel(mem.emotion)}
                </span>
                {mem.is_core && (
                  <span style={{ padding: '2px 8px', borderRadius: '10px', fontSize: '11px', background: '#f59e0b', color: '#000' }}>
                    核心记忆
                  </span>
                )}
              </div>
              <div style={{ display: 'flex', gap: '12px', fontSize: '11px', color: '#555' }}>
                <span>重要性: {mem.importance.toFixed(2)}</span>
                <span>Tick: {mem.tick_created}</span>
              </div>
            </div>
            <div style={{ fontSize: '14px', color: '#e0e0e0', lineHeight: '1.5', marginBottom: '8px' }}>
              {mem.content}
            </div>
            {mem.context && (
              <div style={{ fontSize: '11px', color: '#666', fontStyle: 'italic' }}>
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
              borderRadius: '6px',
              border: 'none',
              background: page <= 1 ? '#333' : '#2a2a4e',
              color: page <= 1 ? '#666' : '#fff',
              cursor: page <= 1 ? 'not-allowed' : 'pointer',
            }}
          >
            上一页
          </button>
          <span style={{ color: '#888', fontSize: '12px', lineHeight: '32px' }}>
            第 {page} / {totalPages} 页，共 {total} 条
          </span>
          <button
            onClick={() => setPage(p => p + 1)}
            disabled={page >= totalPages}
            style={{
              padding: '6px 12px',
              borderRadius: '6px',
              border: 'none',
              background: page >= totalPages ? '#333' : '#2a2a4e',
              color: page >= totalPages ? '#666' : '#fff',
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
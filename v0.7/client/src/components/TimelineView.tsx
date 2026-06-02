/**
 * TimelineView.tsx — V0.7 世界时间线组件
 * 显示世界大事记和角色对话里程碑
 */

import { useEffect, useState } from 'react'

export interface TimelineEvent {
  id?: string
  event_type: string
  description: string
  participants: string[]
  tick: number
  timestamp?: string
}

interface TimelineViewProps {
  events: TimelineEvent[]
  setEvents: (e: TimelineEvent[]) => void
}

function TimelineView({ events, setEvents }: TimelineViewProps) {
  const [loading, setLoading] = useState(false)
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [filterType, setFilterType] = useState<string>('')
  const pageSize = 20

  useEffect(() => {
    fetchTimeline(page, filterType)
  }, [page, filterType])

  const fetchTimeline = async (pageNum: number, eventType: string) => {
    setLoading(true)
    try {
      let url = `/world/timeline?page=${pageNum}&size=${pageSize}`
      if (eventType) {
        url += `&event_type=${encodeURIComponent(eventType)}`
      }
      const resp = await fetch(url)
      const data = await resp.json()
      setEvents(data.events || [])
      setTotal(data.total || 0)
    } catch (e) {
      console.error('获取时间线失败:', e)
    }
    setLoading(false)
  }

  const eventTypeColor = (type: string) => {
    switch (type) {
      case 'dialogue': return 'var(--accent-blue)'
      case 'action': return '#10b981'
      case 'system': return 'var(--accent-yellow)'
      case 'narrative': return 'var(--accent-purple)'
      case 'world': return 'var(--accent-red)'
      default: return 'var(--text-secondary)'
    }
  }

  const eventTypeLabel = (type: string) => {
    switch (type) {
      case 'dialogue': return '对话'
      case 'action': return '动作'
      case 'system': return '系统'
      case 'narrative': return '叙事'
      case 'world': return '世界'
      default: return type
    }
  }

  const totalPages = Math.ceil(total / pageSize)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: '12px' }}>
      {/* 筛选器 */}
      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', flexShrink: 0 }}>
        <span style={{ color: 'var(--text-secondary)', fontSize: '12px', lineHeight: '32px' }}>筛选:</span>
        {['', 'dialogue', 'action', 'system', 'narrative'].map(type => (
          <button
            key={type || 'all'}
            onClick={() => { setFilterType(type); setPage(1) }}
            style={{
              padding: '6px 12px',
              borderRadius: '16px',
              border: 'none',
              background: filterType === type ? 'var(--accent-cyan)' : 'var(--bg-tertiary)',
              color: filterType === type ? '#000' : '#fff',
              cursor: 'pointer',
              fontSize: '12px',
              fontWeight: 'bold',
            }}
          >
            {type ? eventTypeLabel(type) : '全部'}
          </button>
        ))}
      </div>

      {/* 时间线内容 */}
      <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0' }}>
        {loading && (
          <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '40px', fontSize: '14px' }}>
            加载中...
          </div>
        )}
        {!loading && events.length === 0 && (
          <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '40px', fontSize: '14px' }}>
            暂无事件记录
          </div>
        )}
        {!loading && events.map((event, idx) => (
          <div
            key={event.id || idx}
            style={{
              display: 'flex',
              gap: '12px',
              padding: '12px 0',
              borderBottom: '1px solid var(--border-default)',
            }}
          >
            {/* 时间线点 */}
            <div style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              background: eventTypeColor(event.event_type),
              marginTop: '6px',
              flexShrink: 0,
            }} />

            {/* 内容 */}
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', gap: '8px', marginBottom: '4px', alignItems: 'center' }}>
                <span
                  style={{
                    padding: '2px 8px',
                    borderRadius: '10px',
                    fontSize: '11px',
                    background: 'var(--bg-tertiary)',
                    color: eventTypeColor(event.event_type),
                  }}
                >
                  {eventTypeLabel(event.event_type)}
                </span>
                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                  Tick {event.tick}
                </span>
              </div>
              <div style={{ fontSize: '14px', color: 'var(--text-primary)', lineHeight: '1.5', marginBottom: '4px' }}>
                {event.description}
              </div>
              {event.participants && event.participants.length > 0 && (
                <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                  参与者: {event.participants.join(', ')}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* 分页 */}
      {total > 0 && (
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

export default TimelineView
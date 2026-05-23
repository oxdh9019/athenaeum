/**
 * TimelineView.tsx — V0.6 世界时间线组件
 * 显示世界大事记和角色对话里程碑
 */

import { useEffect, useState } from 'react'

interface TimelineEvent {
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
      case 'dialogue': return '#3b82f6'
      case 'action': return '#10b981'
      case 'system': return '#f59e0b'
      case 'narrative': return '#a78bfa'
      case 'world': return '#ef4444'
      default: return '#888'
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
        <span style={{ color: '#888', fontSize: '12px', lineHeight: '32px' }}>筛选:</span>
        {['', 'dialogue', 'action', 'system', 'narrative'].map(type => (
          <button
            key={type || 'all'}
            onClick={() => { setFilterType(type); setPage(1) }}
            style={{
              padding: '6px 12px',
              borderRadius: '16px',
              border: 'none',
              background: filterType === type ? '#00d4ff' : '#2a2a4e',
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
          <div style={{ color: '#666', textAlign: 'center', padding: '40px', fontSize: '14px' }}>
            加载中...
          </div>
        )}
        {!loading && events.length === 0 && (
          <div style={{ color: '#666', textAlign: 'center', padding: '40px', fontSize: '14px' }}>
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
              borderBottom: '1px solid #2a2a4e',
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
                    background: '#2a2a4e',
                    color: eventTypeColor(event.event_type),
                  }}
                >
                  {eventTypeLabel(event.event_type)}
                </span>
                <span style={{ fontSize: '11px', color: '#555' }}>
                  Tick {event.tick}
                </span>
              </div>
              <div style={{ fontSize: '14px', color: '#e0e0e0', lineHeight: '1.5', marginBottom: '4px' }}>
                {event.description}
              </div>
              {event.participants && event.participants.length > 0 && (
                <div style={{ fontSize: '11px', color: '#666' }}>
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

export default TimelineView
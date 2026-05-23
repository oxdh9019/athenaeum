import { useState, useEffect, useCallback, useRef } from 'react'
import Worldsmith from '../../../v0.4/Worldsmith.tsx'
import DiaryView from './DiaryView'
import TimelineView from './TimelineView'
import Dashboard from './components/Dashboard'
import TopBar from './components/TopBar'
import RoleCards from './components/RoleCards'
import ActionStream from './components/ActionStream'

interface Agent {
  id: string
  name: string
  location: string
  neighbors: string[]
  is_active: boolean
  personality?: {
    openness: number
    conscientiousness: number
    extraversion: number
    agreeableness: number
    neuroticism: number
  }
  mood?: string
  intention?: string
  desires?: {
    safety: number
    belonging: number
    novelty: number
  }
}

interface Location {
  id: string
  name: string
  tags: string[]
  agents: string[]
}

interface DialogueEntry {
  from: string
  from_id: string
  to: string
  utterance: string
  tick: number
}

interface ActionEntry {
  agent_id: string
  agent_name: string
  action_type: string
  description: string
  target_location: string | null
  tick: number
}

interface WorldState {
  tick_id: number
  time: { game_hour: number; time_of_day: string }
  weather: string
  tick_type: string
  agents: Agent[]
  locations: Location[]
  recent_dialogues: DialogueEntry[]
  recent_actions: ActionEntry[]
}

type ViewMode = 'observe' | 'possess' | 'editor' | 'worldsmith' | 'diary' | 'timeline' | 'dashboard'

function App() {
  const [ws, setWs] = useState<WebSocket | null>(null)
  const [worldState, setWorldState] = useState<WorldState | null>(null)
  const [viewMode, setViewMode] = useState<ViewMode>('worldsmith')
  const [possessAgent, setPossessAgent] = useState<string>('')
  const [message, setMessage] = useState('')
  const [connected, setConnected] = useState(false)
  const [paused, setPaused] = useState(false)
  const [dialogueLog, setDialogueLog] = useState<DialogueEntry[]>([])
  const [actionLog, setActionLog] = useState<ActionEntry[]>([])
  const [diaryMemories, setDiaryMemories] = useState<any[]>([])
  const [selectedDiaryAgent, setSelectedDiaryAgent] = useState<string>('')
  const [timelineEvents, setTimelineEvents] = useState<any[]>([])
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null)
  const [routerStats, setRouterStats] = useState<any>(null)
  const logEndRef = useRef<HTMLDivElement>(null)
  const actionLogEndRef = useRef<HTMLDivElement>(null)

  // 获取路由统计
  useEffect(() => {
    const fetchRouterStats = async () => {
      try {
        const res = await fetch('/router/stats')
        if (res.ok) {
          const stats = await res.json()
          setRouterStats(stats)
        }
      } catch {}
    }
    const interval = setInterval(fetchRouterStats, 10000)
    fetchRouterStats()
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    const websocket = new WebSocket(`ws://${window.location.host}/ws`)

    websocket.onopen = () => {
      setConnected(true)
      console.log('[WS] Connected')
    }

    websocket.onmessage = (event) => {
      const data = JSON.parse(event.data)
      if (data.recent_dialogues && data.recent_dialogues.length > 0) {
        setDialogueLog(prev => {
          const newEntries = data.recent_dialogues.filter(
            (d: DialogueEntry) => !prev.some(p => p.tick === d.tick && p.from === d.from && p.utterance === d.utterance)
          )
          return newEntries.length > 0 ? [...prev, ...newEntries] : prev
        })
      }
      if (data.recent_actions && data.recent_actions.length > 0) {
        setActionLog(prev => {
          const newEntries = data.recent_actions.filter(
            (a: ActionEntry) => !prev.some(p => p.tick === a.tick && p.agent_id === a.agent_id && p.description === a.description)
          )
          return newEntries.length > 0 ? [...prev, ...newEntries] : prev
        })
      }
      setWorldState(data)
    }

    websocket.onclose = () => {
      setConnected(false)
      console.log('[WS] Disconnected')
    }

    setWs(websocket)

    return () => {
      websocket.close()
    }
  }, [])

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [dialogueLog])

  useEffect(() => {
    actionLogEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [actionLog])

  const handlePossess = useCallback(() => {
    if (!possessAgent || !message) return
    ws?.send(JSON.stringify({ type: 'possess', agent_id: possessAgent, message }))
    setMessage('')
  }, [ws, possessAgent, message])

  const handleRelease = useCallback(() => {
    ws?.send(JSON.stringify({ type: 'release' }))
    setPossessAgent('')
  }, [ws])

  const togglePause = useCallback(() => {
    const newPaused = !paused
    setPaused(newPaused)
    fetch(newPaused ? '/engine/pause' : '/engine/resume', { method: 'POST' })
      .then(res => res.json())
      .catch(console.error)
  }, [ws, paused])

  const handleDiaryClick = useCallback((agentId: string) => {
    setSelectedDiaryAgent(agentId)
    setViewMode('diary')
  }, [])

  // 构建互动舞台的条目列表
  const streamEntries = [
    ...dialogueLog.map(d => ({
      id: `d-${d.tick}-${d.from}-${d.utterance.slice(0, 20)}`,
      type: 'dialogue' as const,
      agentName: d.from,
      agentId: d.from_id,
      content: d.utterance,
      tick: d.tick,
    })),
    ...actionLog.map(a => ({
      id: `a-${a.tick}-${a.agent_id}-${a.description.slice(0, 20)}`,
      type: 'action' as const,
      agentName: a.agent_name,
      agentId: a.agent_id,
      content: a.description,
      tick: a.tick,
    })),
  ].sort((a, b) => a.tick - b.tick)

  const renderMainContent = () => {
    if (viewMode === 'worldsmith') {
      return (
        <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
          <Worldsmith />
        </div>
      )
    }

    if (viewMode === 'diary') {
      return (
        <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
          <DiaryView
            agents={worldState?.agents || []}
            selectedAgent={selectedDiaryAgent}
            onSelectAgent={setSelectedDiaryAgent}
            memories={diaryMemories}
            setMemories={setDiaryMemories}
          />
        </div>
      )
    }

    if (viewMode === 'timeline') {
      return (
        <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
          <TimelineView events={timelineEvents} setEvents={setTimelineEvents} />
        </div>
      )
    }

    if (viewMode === 'dashboard') {
      return (
        <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
          <Dashboard />
        </div>
      )
    }

    // 旁观/附身模式：互动舞台
    return (
      <ActionStream
        entries={streamEntries}
        style={{ flex: 1 }}
      />
    )
  }

  return (
    <div style={{
      height: '100vh',
      display: 'flex',
      flexDirection: 'column',
      background: '#0f0f1a',
      overflow: 'hidden',
    }}>
      {/* 世界底色栏 */}
      <TopBar
        gameHour={worldState?.time.game_hour ?? 8}
        timeOfDay={worldState?.time.time_of_day ?? 'morning'}
        weather={worldState?.weather ?? 'clear'}
        tickId={worldState?.tick_id ?? 0}
        tickType={worldState?.tick_type ?? 'SILENT'}
        routerStats={routerStats}
      />

      {/* 主内容区（世界工坊模式除外） */}
      {viewMode !== 'worldsmith' && worldState ? (
        <div style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          minHeight: 0,
        }}>
          {/* 上半：角色卡片区（固定高度） */}
          <RoleCards
            agents={worldState?.agents || []}
            selectedAgent={selectedAgent}
            onSelectAgent={setSelectedAgent}
            onDiaryClick={handleDiaryClick}
            style={{ flex: 1 }}
          />

          {/* 下半：互动舞台（撑满剩余空间） */}
          <div style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            minHeight: 0,
          }}>
            {renderMainContent()}
          </div>
        </div>
      ) : (
        /* 世界工坊模式：全屏显示 */
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <Worldsmith />
        </div>
      )}

      {/* 底栏控制条（始终显示） */}
      <div style={{
        height: '56px',
        background: '#1a1a2e',
        borderTop: '1px solid #2a2a4e',
        display: 'flex',
        alignItems: 'center',
        padding: '0 16px',
        gap: '16px',
        flexShrink: 0,
      }}>
        {/* 状态 */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{ color: connected ? '#4ade80' : '#ef4444', fontSize: '12px' }}>
            {connected ? '● 已连接' : '○ 未连接'}
          </span>
          {worldState && (
            <span style={{ color: '#666', fontSize: '12px' }}>
              {worldState.agents.length} 角色 · {worldState.locations.length} 地点
            </span>
          )}
        </div>

        {/* 暂停按钮（仅在有世界状态时可用） */}
        {worldState && (
          <button
            onClick={togglePause}
            style={{
              padding: '6px 16px',
              borderRadius: '6px',
              border: 'none',
              background: paused ? '#22c55e' : '#f59e0b',
              color: '#fff',
              cursor: 'pointer',
              fontSize: '12px',
              fontWeight: 'bold',
            }}
          >
            {paused ? '▶️ 继续' : '⏸️ 暂停'}
          </button>
        )}

        {/* 视图切换 */}
        <div style={{ display: 'flex', gap: '8px', marginLeft: 'auto' }}>
          {(['observe', 'possess', 'diary', 'timeline', 'worldsmith'] as ViewMode[]).map(mode => (
            <button
              key={mode}
              onClick={() => setViewMode(mode)}
              style={{
                padding: '6px 12px',
                borderRadius: '6px',
                border: 'none',
                background: viewMode === mode ? '#00d4ff' : '#2a2a4e',
                color: viewMode === mode ? '#000' : '#888',
                cursor: 'pointer',
                fontSize: '12px',
              }}
            >
              {mode === 'observe' && '👁️ 旁观'}
              {mode === 'possess' && '🎭 附身'}
              {mode === 'diary' && '📔 日记'}
              {mode === 'timeline' && '📜 时间线'}
              {mode === 'worldsmith' && '🔨 工坊'}
            </button>
          ))}
        </div>

        {/* 附身输入（仅附身模式且有possessAgent时显示） */}
        {viewMode === 'possess' && possessAgent && (
          <div style={{ display: 'flex', gap: '8px', marginLeft: '16px' }}>
            <input
              type="text"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handlePossess()}
              placeholder="输入要说的话..."
              style={{
                padding: '6px 12px',
                borderRadius: '6px',
                border: '1px solid #3a3a5e',
                background: '#1a1a2e',
                color: '#fff',
                fontSize: '12px',
                width: '200px',
              }}
            />
            <button
              onClick={handlePossess}
              style={{
                padding: '6px 12px',
                borderRadius: '6px',
                border: 'none',
                background: '#4ade80',
                color: '#000',
                cursor: 'pointer',
                fontSize: '12px',
                fontWeight: 'bold',
              }}
            >
              发送
            </button>
            <button
              onClick={handleRelease}
              style={{
                padding: '6px 12px',
                borderRadius: '6px',
                border: 'none',
                background: '#ef4444',
                color: '#fff',
                cursor: 'pointer',
                fontSize: '12px',
              }}
            >
              释放
            </button>
          </div>
        )}
      </div>

      {/* 加载状态 */}
      {!worldState && viewMode !== 'worldsmith' && (
        <div style={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          color: '#888',
          fontSize: '14px',
        }}>
          🌍 正在连接世界引擎...
        </div>
      )}
    </div>
  )
}

export default App
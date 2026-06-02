/**
 * App.tsx — V0.7 模块化主应用
 * 使用 Tab 导航，集成 Dashboard/Agents/Dialogue/Soul/Diary/Timeline/Map/Possess 视图
 */

import { useState, useEffect, useRef, useCallback } from 'react'
import './styles/global.css'
import { WorldProvider } from './context/WorldContext'
import { useWorldSocket } from './hooks/useWorldSocket'
import { ErrorBoundary } from './components/ErrorBoundary'
import TopBar from './components/TopBar'
import ControlBar from './components/ControlBar'
import RoleCards from './components/RoleCards'
import DiaryView from './components/DiaryView'
import TimelineView from './components/TimelineView'
import MapCanvas from './components/MapCanvas'
import PossessMode, { type PossessTurn } from './components/PossessMode'
import Worldsmith from './components/Worldsmith'
import {
  WorldStateSchema,
  RouterStatsSchema,
  HealthResponseSchema,
  fetchJson,
  type Agent,
  type WorldState,
  type DialogueEntry,
  type RouterStats,
} from './types/api'
import type { Memory } from './components/DiaryView'
import type { TimelineEvent } from './components/TimelineView'
import Dashboard from './views/Dashboard'
import AgentsView from './views/AgentsView'
import DialogueView from './views/DialogueView'
import SoulView from './views/SoulView'
import { T } from './constants/zh-CN'

const API_BASE = 'http://localhost:8000'

type ViewMode = 'dashboard' | 'agents' | 'dialogue' | 'soul' | 'diary' | 'timeline' | 'map' | 'possess' | 'worldsmith'

function AppContent() {
  const [viewMode, setViewMode] = useState<ViewMode>('dashboard')
  const [worldState, setWorldState] = useState<WorldState | null>(null)
  const [connected, setConnected] = useState(false)
  const [dialogues, setDialogues] = useState<DialogueEntry[]>([])
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null)
  const [agents, setAgents] = useState<Agent[]>([])
  const [routerStats, setRouterStats] = useState<RouterStats | undefined>(undefined)
  const [paused, setPaused] = useState(false)
  const [possessAgent, setPossessAgent] = useState<Agent | null>(null)
  const [possessTurns, setPossessTurns] = useState<PossessTurn[]>([])
  const [possessPending, setPossessPending] = useState(false)
  const [diaryMemories, setDiaryMemories] = useState<Memory[]>([])
  const [timelineEvents, setTimelineEvents] = useState<TimelineEvent[]>([])
  const dialogueScrollRef = useRef<HTMLDivElement>(null)

  // WS 驱动的实时状态推送；轮询仅作为 WS 断线时的兜底
  const { connectionState, send: wsSend } = useWorldSocket({
    onMessage: (data) => {
      if (data?.type === 'state' && (data as { data?: unknown }).data) {
        const parsed = WorldStateSchema.safeParse((data as { data: unknown }).data)
        if (parsed.success) {
          setWorldState(parsed.data)
          setAgents(parsed.data.agents)
          setDialogues(parsed.data.recent_dialogues)
          setConnected(true)
        }
      }
    },
    onPossessReply: ({ agent_id, text }) => {
      setPossessPending(false)
      setPossessTurns(prev => [...prev, { role: 'agent', text, ts: Date.now() }])
      // 同步更新该 agent 的情绪/状态(可选)
      setAgents(prev => prev.map(a => a.id === agent_id ? { ...a } : a))
    },
    onClose: () => setConnected(false),
  })

  // 健康探测 + 路由统计：单独轮询（不需要 WS 推送）
  useEffect(() => {
    const probeHealth = async () => {
      const health = await fetchJson(`${API_BASE}/health`, HealthResponseSchema)
      if (health) {
        setConnected(health.status === 'healthy')
        if (health.status === 'healthy' && !worldState) fetchState()
      }
    }
    probeHealth()
    const healthInterval = setInterval(probeHealth, 30000)  // 30s 心跳，不再 3s 轮询
    const statsInterval = setInterval(fetchRouterStats, 10000)
    // WS 长时间没连接时降级为轮询
    let pollFallback: ReturnType<typeof setInterval> | null = null
    if (connectionState !== 'connected') {
      pollFallback = setInterval(fetchState, 5000)
    }
    return () => {
      clearInterval(healthInterval)
      clearInterval(statsInterval)
      if (pollFallback) clearInterval(pollFallback)
    }
  }, [connectionState])

  const fetchState = async () => {
    const data = await fetchJson(`${API_BASE}/world/state`, WorldStateSchema)
    if (data) {
      setWorldState(data)
      setAgents(data.agents)
      setDialogues(data.recent_dialogues)
    }
  }

  const fetchRouterStats = async () => {
    const stats = await fetchJson(`${API_BASE}/router/stats`, RouterStatsSchema)
    setRouterStats(stats ?? undefined)
  }

  const createWorld = async () => {
    await fetch(`${API_BASE}/world/create`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: 'Athenaeum',
        locations: ['图书馆', '咖啡厅', '公园', '街道']
      })
    })
    fetchState()
  }

  const createAgent = async (name: string, occupation: string, location: string) => {
    const id = name.toLowerCase().replace(/\s/g, '_')
    await fetch(`${API_BASE}/agent/create`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        id, name, occupation, initial_location: location,
        personality: {
          openness: 0.6 + Math.random() * 0.3,
          conscientiousness: 0.5 + Math.random() * 0.3,
          extraversion: 0.4 + Math.random() * 0.4,
          agreeableness: 0.5 + Math.random() * 0.3,
          neuroticism: 0.3 + Math.random() * 0.3,
        }
      })
    })
    fetchState()
  }

  const startDialogue = async (agentA: string, agentB: string) => {
    await fetch(`${API_BASE}/dialogue/start?agent_a=${agentA}&agent_b=${agentB}`, {
      method: 'POST'
    })
  }

  const handleApplyToEngine = async () => {
    await fetchState()
    setViewMode('dashboard')
  }

  const startWorld = async () => {
    await fetch(`${API_BASE}/world/start`, { method: 'POST' })
    fetchState()
  }

  const togglePause = async () => {
    const newPaused = !paused
    setPaused(newPaused)
    await fetch(newPaused ? `${API_BASE}/engine/pause` : `${API_BASE}/engine/resume`, { method: 'POST' })
  }

  const handleStop = async () => {
    if (confirm('确定要停止服务器吗？')) {
      try {
        await fetch(`${API_BASE}/server/stop`, { method: 'POST' })
        // 后端会优雅退出。window.close() 在大多数浏览器无效，
        // 改为显示提示，让用户手动关闭 tab。
        alert('服务器已停止。请刷新页面或手动关闭此标签页。')
      } catch {
        alert('服务器已停止。请刷新页面或手动关闭此标签页。')
      }
    }
  }

  const handlePossessSend = useCallback((message: string) => {
    if (!possessAgent) return
    setPossessTurns(prev => [...prev, { role: 'user', text: message, ts: Date.now() }])
    setPossessPending(true)
    wsSend({
      type: 'possess_message',
      agent_id: possessAgent.id,
      message,
    })
  }, [possessAgent, wsSend])

  const handlePossessRelease = () => {
    setPossessAgent(null)
    setPossessTurns([])
    setPossessPending(false)
    wsSend({ type: 'release', agent_id: possessAgent?.id })
  }

  useEffect(() => {
    const el = dialogueScrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [dialogues])

  const renderMainContent = () => {
    switch (viewMode) {
      case 'dashboard':
        return <Dashboard agents={agents} onCreateAgent={createAgent} worldState={worldState} onCreateWorld={createWorld} onStartWorld={startWorld} />
      case 'agents':
        return <AgentsView agents={agents} selectedAgent={selectedAgent} onSelectAgent={setSelectedAgent} />
      case 'dialogue':
        return <DialogueView dialogues={dialogues} agents={agents} onStartDialogue={startDialogue} scrollRef={dialogueScrollRef} />
      case 'soul':
        return <SoulView agent={selectedAgent} />
      case 'diary':
        return (
          <DiaryView
            agents={agents}
            selectedAgent={selectedAgent?.id || ''}
            onSelectAgent={(id) => setSelectedAgent(agents.find(a => a.id === id) || null)}
            memories={diaryMemories}
            setMemories={setDiaryMemories}
          />
        )
      case 'timeline':
        return <TimelineView events={timelineEvents} setEvents={setTimelineEvents} />
      case 'map':
        return (
          <MapCanvas
            agents={agents}
            locations={worldState?.locations ?? []}
            onAgentClick={(id) => {
              const agent = agents.find(a => a.id === id)
              if (agent) setSelectedAgent(agent)
            }}
          />
        )
      case 'possess':
        return (
          <PossessMode
            agent={possessAgent}
            onSend={handlePossessSend}
            onRelease={handlePossessRelease}
            turns={possessTurns}
            pending={possessPending}
          />
        )
      case 'worldsmith':
        return <Worldsmith onApplyToEngine={handleApplyToEngine} />
      default:
        return null
    }
  }

  return (
    <div className="app-container">
      {/* Header */}
      <header className="app-header">
        <div className="app-logo">
          <h1>{T.app.title}</h1>
          <span className="version">{T.app.version}</span>
        </div>
        <nav className="app-nav">
          <button className={`nav-btn ${viewMode === 'dashboard' ? 'active' : ''}`} onClick={() => setViewMode('dashboard')}>{T.tabs.dashboard}</button>
          <button className={`nav-btn ${viewMode === 'agents' ? 'active' : ''}`} onClick={() => setViewMode('agents')}>{T.tabs.agents}</button>
          <button className={`nav-btn ${viewMode === 'dialogue' ? 'active' : ''}`} onClick={() => setViewMode('dialogue')}>{T.tabs.dialogue}</button>
          <button className={`nav-btn ${viewMode === 'soul' ? 'active' : ''}`} onClick={() => setViewMode('soul')}>{T.tabs.soul}</button>
          <button className={`nav-btn ${viewMode === 'worldsmith' ? 'active' : ''}`} onClick={() => setViewMode('worldsmith')}>{T.tabs.worldsmith}</button>
          <button className={`nav-btn ${viewMode === 'diary' ? 'active' : ''}`} onClick={() => setViewMode('diary')}>{T.tabs.diary}</button>
          <button className={`nav-btn ${viewMode === 'timeline' ? 'active' : ''}`} onClick={() => setViewMode('timeline')}>{T.tabs.timeline}</button>
          <button className={`nav-btn ${viewMode === 'map' ? 'active' : ''}`} onClick={() => setViewMode('map')}>{T.tabs.map}</button>
          <button className={`nav-btn ${viewMode === 'possess' ? 'active' : ''}`} onClick={() => setViewMode('possess')}>{T.tabs.possess}</button>
        </nav>
        <div className="app-status">
          <span className={`status-dot ${connected ? 'connected' : 'disconnected'}`} />
          {connected ? T.app.statusConnected : T.app.statusDisconnected}
        </div>
      </header>

      {/* TopBar */}
      <TopBar
        gameHour={worldState?.time?.game_hour ?? 8}
        timeOfDay={worldState?.time?.time_of_day ?? 'morning'}
        weather={worldState?.weather ?? 'clear'}
        tickId={worldState?.tick_id ?? 0}
        tickType={worldState?.tick_type ?? 'SILENT'}
        routerStats={routerStats}
      />

      {/* RoleCards */}
      {viewMode !== 'dashboard' && viewMode !== 'possess' && (
        <RoleCards
          agents={agents}
          selectedAgent={selectedAgent?.id ?? null}
          onSelectAgent={(id) => setSelectedAgent(agents.find(a => a.id === id) || null)}
          onDiaryClick={(id) => {
            const agent = agents.find(a => a.id === id)
            if (agent) {
              setSelectedAgent(agent)
              setPossessAgent(agent)
              setViewMode('possess')
            }
          }}
          style={{ height: '160px' }}
        />
      )}

      {/* Main Content */}
      <main className="app-main">
        <ErrorBoundary>
          {renderMainContent()}
        </ErrorBoundary>
      </main>

      {/* ControlBar */}
      <ControlBar
        connectionState={connected ? 'connected' : 'disconnected'}
        paused={paused}
        tickId={worldState?.tick_id ?? 0}
        gameHour={worldState?.time?.game_hour ?? 8}
        timeOfDay={worldState?.time?.time_of_day ?? 'morning'}
        weather={worldState?.weather ?? 'clear'}
        onTogglePause={togglePause}
        onStop={handleStop}
        viewMode={viewMode}
        onViewModeChange={(v) => setViewMode(v as ViewMode)}
      />
    </div>
  )
}

// ==================== 子视图组件 ====================
// 已迁移至 src/views/{Dashboard,AgentsView,DialogueView,SoulView}.tsx

function App() {
  return (
    <WorldProvider>
      <AppContent />
    </WorldProvider>
  )
}

export default App
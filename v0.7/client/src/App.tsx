import { useState, useEffect, useRef } from 'react'

const API_BASE = 'http://localhost:8000'

interface Agent {
  id: string
  name: string
  location: string
  occupation?: string
  personality?: Record<string, number>
  soul?: {
    core_desires?: Array<{ name: string; level: number }>
    inner_conflict?: { description: string }
    subconscious_rules?: Array<{ trigger: string; action: string }>
  }
  emotion_state?: { label: string; valence: number; arousal: number }
  active_goal?: string
  goal_progress?: number
}

interface DialogueEntry {
  from: string
  to: string
  utterance: string
  micro_action?: string
  tick: number
}

interface WorldState {
  tick_id: number
  time_of_day: string
  weather: string
  agents: Agent[]
  locations: string[]
  dialogues: DialogueEntry[]
}

type ViewMode = 'dashboard' | 'agents' | 'dialogue' | 'soul' | 'world'

function App() {
  const [viewMode, setViewMode] = useState<ViewMode>('dashboard')
  const [worldState, setWorldState] = useState<WorldState | null>(null)
  const [connected, setConnected] = useState(false)
  const [dialogues, setDialogues] = useState<DialogueEntry[]>([])
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null)
  const [agents, setAgents] = useState<Agent[]>([])
  const dialogueEndRef = useRef<HTMLDivElement>(null)

  // 连接后端 WebSocket 或轮询
  useEffect(() => {
    const connect = async () => {
      try {
        const res = await fetch(`${API_BASE}/health`)
        if (res.ok) {
          setConnected(true)
          fetchState()
        }
      } catch {
        setConnected(false)
      }
    }
    connect()
    const interval = setInterval(fetchState, 3000)
    return () => clearInterval(interval)
  }, [])

  const fetchState = async () => {
    try {
      const res = await fetch(`${API_BASE}/world/state`)
      if (res.ok) {
        const data = await res.json()
        setWorldState(data)
        if (data.agents) setAgents(data.agents)
        if (data.dialogues) {
          setDialogues(prev => [...prev, ...data.dialogues].slice(-100))
        }
      }
    } catch {}
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

  const startWorld = async () => {
    await fetch(`${API_BASE}/world/start`, { method: 'POST' })
    fetchState()
  }

  useEffect(() => {
    dialogueEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [dialogues])

  return (
    <div className="app-container">
      {/* Header */}
      <header style={styles.header}>
        <div style={styles.logo}>
          <h1>🏛️ Athenaeum</h1>
          <span style={styles.version}>V0.7 灵魂增强版</span>
        </div>
        <nav style={styles.nav}>
          <button style={{...styles.navBtn, ...(viewMode === 'dashboard' ? styles.navBtnActive : {})}} onClick={() => setViewMode('dashboard')}>概览</button>
          <button style={{...styles.navBtn, ...(viewMode === 'agents' ? styles.navBtnActive : {})}} onClick={() => setViewMode('agents')}>角色</button>
          <button style={{...styles.navBtn, ...(viewMode === 'dialogue' ? styles.navBtnActive : {})}} onClick={() => setViewMode('dialogue')}>对话</button>
          <button style={{...styles.navBtn, ...(viewMode === 'soul' ? styles.navBtnActive : {})}} onClick={() => setViewMode('soul')}>灵魂</button>
        </nav>
        <div style={styles.status}>
          <span style={{...styles.statusDot, background: connected ? '#4ade80' : '#ef4444'}} />
          {connected ? '已连接' : '未连接'}
        </div>
      </header>

      {/* Main Content */}
      <main style={styles.main}>
        {viewMode === 'dashboard' && (
          <Dashboard
            worldState={worldState}
            agents={agents}
            onCreateWorld={createWorld}
            onStartWorld={startWorld}
            onCreateAgent={createAgent}
          />
        )}
        {viewMode === 'agents' && (
          <AgentsView
            agents={agents}
            selectedAgent={selectedAgent}
            onSelectAgent={setSelectedAgent}
            onCreateAgent={createAgent}
          />
        )}
        {viewMode === 'dialogue' && (
          <DialogueView
            dialogues={dialogues}
            agents={agents}
            onStartDialogue={startDialogue}
          />
        )}
        {viewMode === 'soul' && (
          <SoulView agent={selectedAgent} />
        )}
      </main>
    </div>
  )
}

function Dashboard({ worldState, agents, onCreateWorld, onStartWorld, onCreateAgent }: any) {
  const [newAgent, setNewAgent] = useState({ name: '', occupation: '', location: '图书馆' })

  return (
    <div style={styles.dashboard}>
      <div style={styles.card}>
        <h3 style={styles.cardTitle}>世界状态</h3>
        <div style={styles.statGrid}>
          <div style={styles.stat}>
            <span style={styles.statValue}>{worldState?.tick_id || 0}</span>
            <span style={styles.statLabel}>Tick</span>
          </div>
          <div style={styles.stat}>
            <span style={styles.statValue}>{worldState?.time_of_day || '--'}</span>
            <span style={styles.statLabel}>时间</span>
          </div>
          <div style={styles.stat}>
            <span style={styles.statValue}>{agents.length}</span>
            <span style={styles.statLabel}>角色数</span>
          </div>
          <div style={styles.stat}>
            <span style={styles.statValue}>{worldState?.locations?.length || 0}</span>
            <span style={styles.statLabel}>地点</span>
          </div>
        </div>
        <div style={styles.actions}>
          <button style={styles.btn} onClick={onCreateWorld}>创建世界</button>
          <button style={styles.btnPrimary} onClick={onStartWorld}>启动世界</button>
        </div>
      </div>

      <div style={styles.card}>
        <h3 style={styles.cardTitle}>创建角色</h3>
        <input style={styles.input} placeholder="角色名" value={newAgent.name} onChange={e => setNewAgent({...newAgent, name: e.target.value})} />
        <input style={styles.input} placeholder="职业" value={newAgent.occupation} onChange={e => setNewAgent({...newAgent, occupation: e.target.value})} />
        <select style={styles.select} value={newAgent.location} onChange={e => setNewAgent({...newAgent, location: e.target.value})}>
          <option value="图书馆">图书馆</option>
          <option value="咖啡厅">咖啡厅</option>
          <option value="公园">公园</option>
        </select>
        <button style={styles.btn} onClick={() => { onCreateAgent(newAgent.name, newAgent.occupation, newAgent.location); setNewAgent({name: '', occupation: '', location: '图书馆'}) }}>添加角色</button>
      </div>

      <div style={styles.card}>
        <h3 style={styles.cardTitle}>活跃角色</h3>
        <div style={styles.agentList}>
          {agents.map((agent: Agent) => (
            <div key={agent.id} style={styles.agentItem}>
              <span style={styles.agentName}>{agent.name}</span>
              <span style={styles.agentLoc}>{agent.location}</span>
            </div>
          ))}
          {agents.length === 0 && <p style={styles.empty}>暂无角色</p>}
        </div>
      </div>
    </div>
  )
}

function AgentsView({ agents, selectedAgent, onSelectAgent, onCreateAgent }: any) {
  return (
    <div style={styles.agentsView}>
      <div style={styles.agentListPanel}>
        <h3 style={styles.cardTitle}>角色列表</h3>
        {agents.map((agent: Agent) => (
          <div key={agent.id} style={{...styles.agentCard, ...(selectedAgent?.id === agent.id ? styles.agentCardSelected : {})}} onClick={() => onSelectAgent(agent)}>
            <div style={styles.agentCardName}>{agent.name}</div>
            <div style={styles.agentCardInfo}>{agent.occupation || '未知职业'} · {agent.location}</div>
          </div>
        ))}
      </div>
      <div style={styles.agentDetail}>
        {selectedAgent ? (
          <>
            <h2 style={styles.detailName}>{selectedAgent.name}</h2>
            <p style={styles.detailOccupation}>{selectedAgent.occupation}</p>
            <div style={styles.detailSection}>
              <h4 style={styles.detailSectionTitle}>情绪状态</h4>
              <p>{selectedAgent.emotion_state?.label || 'neutral'} (效价: {selectedAgent.emotion_state?.valence?.toFixed(2) || '0.00'}, 唤醒: {selectedAgent.emotion_state?.arousal?.toFixed(2) || '0.00'})</p>
            </div>
            <div style={styles.detailSection}>
              <h4 style={styles.detailSectionTitle}>当前目标</h4>
              <p>{selectedAgent.active_goal || '无特定目标'}</p>
              {selectedAgent.goal_progress !== undefined && <p>进度: {(selectedAgent.goal_progress * 100).toFixed(0)}%</p>}
            </div>
            <div style={styles.detailSection}>
              <h4 style={styles.detailSectionTitle}>性格</h4>
              {selectedAgent.personality && Object.entries(selectedAgent.personality).map(([k, v]) => (
                <span key={k} style={styles.personalityTag}>{k}: {(v as number).toFixed(1)}</span>
              ))}
            </div>
          </>
        ) : (
          <p style={styles.empty}>选择角色查看详情</p>
        )}
      </div>
    </div>
  )
}

function DialogueView({ dialogues, agents, onStartDialogue }: any) {
  const [agentA, setAgentA] = useState('')
  const [agentB, setAgentB] = useState('')

  return (
    <div style={styles.dialogueView}>
      <div style={styles.dialogueControls}>
        <select style={styles.select} value={agentA} onChange={e => setAgentA(e.target.value)}>
          <option value="">选择角色 A</option>
          {agents.map((a: Agent) => <option key={a.id} value={a.id}>{a.name}</option>)}
        </select>
        <span>与</span>
        <select style={styles.select} value={agentB} onChange={e => setAgentB(e.target.value)}>
          <option value="">选择角色 B</option>
          {agents.map((a: Agent) => <option key={a.id} value={a.id}>{a.name}</option>)}
        </select>
        <button style={styles.btnPrimary} onClick={() => { if (agentA && agentB) onStartDialogue(agentA, agentB) }}>开始对话</button>
      </div>
      <div style={styles.dialogueLog}>
        {dialogues.map((d: DialogueEntry, i: number) => (
          <div key={i} style={styles.dialogueEntry}>
            <span style={styles.dialogueFrom}>{d.from}:</span>
            <span style={styles.dialogueText}>"{d.utterance}"</span>
            {d.micro_action && <span style={styles.microAction}>*{d.micro_action}*</span>}
          </div>
        ))}
        <div ref={dialogueEndRef} />
      </div>
    </div>
  )
}

function SoulView({ agent }: { agent: Agent | null }) {
  if (!agent) return <p style={styles.empty}>选择角色查看灵魂配置</p>

  return (
    <div style={styles.soulView}>
      <h2 style={styles.detailName}>{agent.name} 的灵魂</h2>
      <div style={styles.card}>
        <h4 style={styles.cardTitle}>核心欲望</h4>
        {agent.soul?.core_desires?.map((d, i) => (
          <div key={i} style={styles.desireItem}>
            <span>{d.name}</span>
            <div style={styles.desireBar}><div style={{...styles.desireFill, width: `${d.level * 100}%`}} /></div>
          </div>
        ))}
      </div>
      <div style={styles.card}>
        <h4 style={styles.cardTitle}>内在矛盾</h4>
        <p>{agent.soul?.inner_conflict?.description || '暂无矛盾描述'}</p>
      </div>
      <div style={styles.card}>
        <h4 style={styles.cardTitle}>潜意识规则</h4>
        {agent.soul?.subconscious_rules?.map((r, i) => (
          <div key={i} style={styles.ruleItem}>
            <span style={styles.ruleTrigger}>"{r.trigger}"</span>
            <span>→ {r.action}</span>
          </div>
        ))}
        {(!agent.soul?.subconscious_rules || agent.soul.subconscious_rules.length === 0) && <p>无潜意识规则</p>}
      </div>
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  header: { display: 'flex', alignItems: 'center', padding: '12px 24px', background: '#1a1a2e', borderBottom: '1px solid #333', gap: '24px' },
  logo: { display: 'flex', alignItems: 'center', gap: '12px' },
  version: { fontSize: '12px', color: '#888' },
  nav: { display: 'flex', gap: '4px', flex: 1 },
  navBtn: { padding: '8px 16px', background: 'transparent', border: 'none', color: '#888', cursor: 'pointer', borderRadius: '6px' },
  navBtnActive: { background: '#3b82f6', color: '#fff' },
  status: { display: 'flex', alignItems: 'center', gap: '8px', fontSize: '14px', color: '#888' },
  statusDot: { width: '8px', height: '8px', borderRadius: '50%' },
  main: { flex: 1, padding: '24px', overflow: 'auto' },
  dashboard: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '20px' },
  card: { background: '#1e1e2e', borderRadius: '12px', padding: '20px', border: '1px solid #333' },
  cardTitle: { fontSize: '14px', color: '#888', marginBottom: '16px', textTransform: 'uppercase', letterSpacing: '1px' },
  statGrid: { display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '16px', marginBottom: '16px' },
  stat: { textAlign: 'center' },
  statValue: { display: 'block', fontSize: '28px', fontWeight: 'bold', color: '#3b82f6' },
  statLabel: { fontSize: '12px', color: '#666' },
  actions: { display: 'flex', gap: '8px' },
  btn: { padding: '10px 20px', background: '#333', border: 'none', color: '#fff', borderRadius: '8px', cursor: 'pointer', flex: 1 },
  btnPrimary: { padding: '10px 20px', background: '#3b82f6', border: 'none', color: '#fff', borderRadius: '8px', cursor: 'pointer', flex: 1 },
  input: { width: '100%', padding: '10px', background: '#2a2a3a', border: '1px solid #444', borderRadius: '6px', color: '#fff', marginBottom: '8px' },
  select: { width: '100%', padding: '10px', background: '#2a2a3a', border: '1px solid #444', borderRadius: '6px', color: '#fff', marginBottom: '8px' },
  agentList: { display: 'flex', flexDirection: 'column', gap: '8px' },
  agentItem: { display: 'flex', justifyContent: 'space-between', padding: '10px', background: '#2a2a3a', borderRadius: '6px' },
  agentName: { fontWeight: 'bold' },
  agentLoc: { color: '#888', fontSize: '14px' },
  empty: { color: '#666', fontStyle: 'italic', padding: '20px', textAlign: 'center' },
  agentsView: { display: 'grid', gridTemplateColumns: '300px 1fr', gap: '20px', height: 'calc(100vh - 150px)' },
  agentListPanel: { background: '#1e1e2e', borderRadius: '12px', padding: '16px', overflow: 'auto' },
  agentCard: { padding: '12px', background: '#2a2a3a', borderRadius: '8px', marginBottom: '8px', cursor: 'pointer', border: '2px solid transparent' },
  agentCardSelected: { borderColor: '#3b82f6' },
  agentCardName: { fontWeight: 'bold', marginBottom: '4px' },
  agentCardInfo: { fontSize: '12px', color: '#888' },
  agentDetail: { background: '#1e1e2e', borderRadius: '12px', padding: '24px', overflow: 'auto' },
  detailName: { fontSize: '24px', marginBottom: '4px' },
  detailOccupation: { color: '#888', marginBottom: '20px' },
  detailSection: { marginBottom: '20px', paddingBottom: '16px', borderBottom: '1px solid #333' },
  detailSectionTitle: { fontSize: '12px', color: '#666', textTransform: 'uppercase', marginBottom: '8px' },
  personalityTag: { display: 'inline-block', padding: '4px 8px', background: '#333', borderRadius: '4px', fontSize: '12px', marginRight: '4px', marginBottom: '4px' },
  dialogueView: { display: 'flex', flexDirection: 'column', height: 'calc(100vh - 150px)' },
  dialogueControls: { display: 'flex', gap: '12px', alignItems: 'center', marginBottom: '20px', padding: '16px', background: '#1e1e2e', borderRadius: '12px' },
  dialogueLog: { flex: 1, background: '#1e1e2e', borderRadius: '12px', padding: '16px', overflow: 'auto' },
  dialogueEntry: { padding: '8px 0', borderBottom: '1px solid #2a2a3a' },
  dialogueFrom: { fontWeight: 'bold', color: '#3b82f6', marginRight: '8px' },
  dialogueText: { color: '#eee' },
  microAction: { display: 'block', fontStyle: 'italic', color: '#888', fontSize: '14px', marginTop: '4px' },
  soulView: { maxWidth: '800px' },
  desireItem: { display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' },
  desireBar: { flex: 1, height: '8px', background: '#333', borderRadius: '4px' },
  desireFill: { height: '100%', background: '#3b82f6', borderRadius: '4px', transition: 'width 0.3s' },
  ruleItem: { padding: '8px', background: '#2a2a3a', borderRadius: '6px', marginBottom: '6px' },
  ruleTrigger: { color: '#f59e0b', fontWeight: 'bold' },
}

export default App
import { useState } from 'react'
import type { Agent, WorldState } from '../types/api'
import { T } from '../constants/zh-CN'

export interface DashboardProps {
  agents: Agent[]
  worldState: WorldState | null
  onCreateAgent: (name: string, occupation: string, location: string) => void
  onCreateWorld: () => void
  onStartWorld: () => void
}

export default function Dashboard({
  agents,
  worldState,
  onCreateAgent,
  onCreateWorld,
  onStartWorld,
}: DashboardProps) {
  const [newAgent, setNewAgent] = useState<{ name: string; occupation: string; location: string }>({
    name: '',
    occupation: '',
    location: T.locations.library,
  })

  const applied = worldState?.applied ?? false
  const engineRunning = worldState?.engine_running ?? false
  const tickId = worldState?.tick_id ?? 0
  const locations = worldState?.locations ?? []

  return (
    <div className="dashboard">
      <div className="card">
        <h3 className="card-title">{T.dashboard.worldStatus}</h3>
        <div className="stat-grid">
          <div className="stat">
            <span className="stat-value">{tickId}</span>
            <span className="stat-label">{T.dashboard.tick}</span>
          </div>
          <div className="stat">
            <span className="stat-value">{worldState?.time?.time_of_day || '--'}</span>
            <span className="stat-label">{T.dashboard.time}</span>
          </div>
          <div className="stat">
            <span className="stat-value">{agents?.length ?? 0}</span>
            <span className="stat-label">{T.dashboard.agentCount}</span>
          </div>
          <div className="stat">
            <span className="stat-value">{locations.length}</span>
            <span className="stat-label">{T.dashboard.locations}</span>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center', margin: '8px 0' }}>
          <span
            style={{
              padding: '2px 10px',
              borderRadius: '12px',
              fontSize: '12px',
              fontWeight: 'bold',
              background: applied ? 'rgba(34, 197, 94, 0.15)' : 'rgba(107, 114, 128, 0.15)',
              color: applied ? 'var(--accent-green, #22c55e)' : 'var(--text-muted, #9ca3af)',
            }}
          >
            {applied ? '✓ 已应用' : '○ 未应用'}
          </span>
          <span
            style={{
              padding: '2px 10px',
              borderRadius: '12px',
              fontSize: '12px',
              fontWeight: 'bold',
              background: engineRunning ? 'rgba(34, 197, 94, 0.15)' : 'rgba(245, 158, 11, 0.15)',
              color: engineRunning ? 'var(--accent-green, #22c55e)' : 'var(--accent-yellow, #f59e0b)',
            }}
          >
            {engineRunning ? '▶ 运行中' : '⏸ 已停止'}
          </span>
        </div>
        <div className="actions">
          <button className="btn" onClick={onCreateWorld} disabled={applied}>{T.dashboard.createWorld}</button>
          <button className="btn-primary" onClick={onStartWorld} disabled={!applied || engineRunning}>{T.dashboard.startWorld}</button>
        </div>
      </div>

      <div className="card">
        <h3 className="card-title">{T.dashboard.createAgent}</h3>
        <input className="input" placeholder={T.dashboard.agentName} value={newAgent.name} onChange={e => setNewAgent({...newAgent, name: e.target.value})} />
        <input className="input" placeholder={T.dashboard.occupation} value={newAgent.occupation} onChange={e => setNewAgent({...newAgent, occupation: e.target.value})} />
        <select className="select" value={newAgent.location} onChange={e => setNewAgent({...newAgent, location: e.target.value})}>
          <option value={T.locations.library}>{T.locations.library}</option>
          <option value={T.locations.cafe}>{T.locations.cafe}</option>
          <option value={T.locations.park}>{T.locations.park}</option>
        </select>
        <button className="btn" onClick={() => {
          onCreateAgent(newAgent.name, newAgent.occupation, newAgent.location)
          setNewAgent({ name: '', occupation: '', location: T.locations.library })
        }}>{T.dashboard.addAgent}</button>
      </div>

      <div className="card">
        <h3 className="card-title">{T.dashboard.activeAgents}</h3>
        <div className="agent-list">
          {agents.map(agent => (
            <div key={agent.id} className="agent-item" style={{ display: 'flex', flexDirection: 'column', gap: '4px', padding: '8px 0', borderBottom: '1px solid var(--border-default, #333)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span className="agent-name" style={{ fontWeight: 'bold' }}>{agent.name}</span>
                <span className="agent-location" style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{agent.location}</span>
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                {agent.current_action ? `${T.dashboard.action ?? '动作'}: ${agent.current_action}` : T.dashboard.idle ?? '待机中'}
                {agent.emotion_state?.label && ` · ${agent.emotion_state.label}`}
              </div>
            </div>
          ))}
          {agents.length === 0 && <p className="empty">{T.dashboard.noAgents}</p>}
        </div>
      </div>
    </div>
  )
}

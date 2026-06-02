import type { Agent } from '../types/api'
import { T } from '../constants/zh-CN'

export interface AgentsViewProps {
  agents: Agent[]
  selectedAgent: Agent | null
  onSelectAgent: (agent: Agent) => void
}

export default function AgentsView({ agents, selectedAgent, onSelectAgent }: AgentsViewProps) {
  return (
    <div className="agents-view">
      <div className="agent-list-panel">
        <h3 className="card-title-alt">{T.agentsView.list}</h3>
        {agents.map(agent => (
          <div
            key={agent.id}
            className={`agent-card ${selectedAgent?.id === agent.id ? 'selected' : ''}`}
            onClick={() => onSelectAgent(agent)}
          >
            <div className="agent-card-name">{agent.name}</div>
            <div className="agent-card-info">{agent.occupation || T.agentsView.unknownOccupation} · {agent.location}</div>
          </div>
        ))}
      </div>
      <div className="agent-detail">
        {selectedAgent ? (
          <>
            <h2 className="detail-name">{selectedAgent.name}</h2>
            <p className="detail-occupation">{selectedAgent.occupation}</p>
            <div className="detail-section">
              <h4 className="detail-section-title">{T.agentsView.emotionState}</h4>
              <p>{selectedAgent.emotion_state?.label || 'neutral'} (效价: {selectedAgent.emotion_state?.valence?.toFixed(2) || '0.00'}, 唤醒: {selectedAgent.emotion_state?.arousal?.toFixed(2) || '0.00'})</p>
            </div>
            <div className="detail-section">
              <h4 className="detail-section-title">{T.agentsView.currentGoal}</h4>
              <p>{typeof selectedAgent.active_goal === 'string' ? selectedAgent.active_goal : (selectedAgent.active_goal?.description ?? T.agentsView.noGoal)}</p>
              {selectedAgent.goal_progress !== undefined && <p>{T.agentsView.progress}: {(selectedAgent.goal_progress * 100).toFixed(0)}%</p>}
            </div>
            <div className="detail-section">
              <h4 className="detail-section-title">{T.agentsView.personality}</h4>
              {selectedAgent.personality && Object.entries(selectedAgent.personality).map(([k, v]) => (
                <span key={k} className="personality-tag">{k}: {Number(v).toFixed(1)}</span>
              ))}
            </div>
          </>
        ) : (
          <p className="empty">{T.agentsView.selectAgent}</p>
        )}
      </div>
    </div>
  )
}

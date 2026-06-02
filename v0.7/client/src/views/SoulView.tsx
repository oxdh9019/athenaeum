import type { Agent } from '../types/api'
import { T } from '../constants/zh-CN'

export interface SoulViewProps {
  agent: Agent | null
}

export default function SoulView({ agent }: SoulViewProps) {
  return (
    <div className="soul-view">
      {!agent && <p className="empty">{T.soulView.selectPrompt}</p>}
      {agent && <>
        <h2 style={{ fontSize: '24px', marginBottom: '4px' }}>{T.soulView.title(agent.name)}</h2>
        <div className="card">
          <h4 className="card-title">{T.soulView.coreDesires}</h4>
          {agent.soul?.core_desires?.map((d, i) => (
            <div key={i} className="desire-item">
              <span>{d.name}</span>
              <div className="desire-bar"><div className="desire-fill" style={{ width: `${d.level * 100}%` }} /></div>
            </div>
          ))}
          {(!agent.soul?.core_desires || agent.soul.core_desires.length === 0) && <p className="empty">{T.soulView.noDesires}</p>}
        </div>
        <div className="card">
          <h4 className="card-title">{T.soulView.innerConflict}</h4>
          <p>{agent.soul?.inner_conflict?.description || T.soulView.noConflict}</p>
        </div>
        <div className="card">
          <h4 className="card-title">{T.soulView.subconsciousRules}</h4>
          {agent.soul?.subconscious_rules?.map((r, i) => (
            <div key={i} className="rule-item">
              <span className="rule-trigger">"{r.trigger}"</span>
              <span>→ {r.action}</span>
            </div>
          ))}
          {(!agent.soul?.subconscious_rules || agent.soul.subconscious_rules.length === 0) && <p className="empty">{T.soulView.noRules}</p>}
        </div>
      </>}
    </div>
  )
}

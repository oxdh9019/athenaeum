import { useState } from 'react'
import type { Agent, DialogueEntry } from '../types/api'
import { T } from '../constants/zh-CN'

export interface DialogueViewProps {
  dialogues: DialogueEntry[]
  agents: Agent[]
  onStartDialogue: (a: string, b: string) => void
  scrollRef?: React.RefObject<HTMLDivElement>
}

export default function DialogueView({ dialogues, agents, onStartDialogue, scrollRef }: DialogueViewProps) {
  const [agentA, setAgentA] = useState('')
  const [agentB, setAgentB] = useState('')

  return (
    <div className="dialogue-view">
      <div className="dialogue-controls">
        <select className="select" value={agentA} onChange={e => setAgentA(e.target.value)} style={{ width: 'auto', flex: 1 }}>
          <option value="">{T.dialogueView.selectAgentA}</option>
          {agents.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
        </select>
        <span>{T.dialogueView.between}</span>
        <select className="select" value={agentB} onChange={e => setAgentB(e.target.value)} style={{ width: 'auto', flex: 1 }}>
          <option value="">{T.dialogueView.selectAgentB}</option>
          {agents.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
        </select>
        <button className="btn-primary" onClick={() => { if (agentA && agentB) onStartDialogue(agentA, agentB) }} style={{ flex: 0 }}>{T.dialogueView.startDialogue}</button>
      </div>
      <div className="dialogue-log" ref={scrollRef}>
        {dialogues.map((d, i) => (
          <div key={i} className="dialogue-entry">
            <span className="dialogue-from">{d.from}:</span>
            <span className="dialogue-text">"{d.utterance}"</span>
            {d.micro_action && <span className="micro-action">*{d.micro_action}*</span>}
          </div>
        ))}
      </div>
    </div>
  )
}

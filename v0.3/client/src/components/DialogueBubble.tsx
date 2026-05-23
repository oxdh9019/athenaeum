/**
 * DialogueBubble.tsx — V0.7 对话气泡组件
 * 在地图上显示角色对话
 */

import { useEffect, useState, useRef } from 'react'
import type { DialogueEntry } from '../context/WorldContext'

interface DialogueBubbleProps {
  dialogues: DialogueEntry[]
  maxVisible?: number
}

function DialogueBubble({ dialogues, maxVisible = 5 }: DialogueBubbleProps) {
  const [visible, setVisible] = useState<DialogueEntry[]>([])
  const prevLengthRef = useRef(0)

  useEffect(() => {
    if (dialogues.length > prevLengthRef.current) {
      const newDialogue = dialogues[dialogues.length - 1]
      setVisible(prev => [...prev.slice(-maxVisible + 1), newDialogue])

      // 3秒后自动消失
      setTimeout(() => {
        setVisible(prev => prev.filter(d => d !== newDialogue))
      }, 3000)
    }
    prevLengthRef.current = dialogues.length
  }, [dialogues, maxVisible])

  return (
    <div style={{
      position: 'fixed',
      top: '80px',
      right: '20px',
      display: 'flex',
      flexDirection: 'column',
      gap: '8px',
      zIndex: 1000,
      pointerEvents: 'none',
    }}>
      {visible.map((dialogue, idx) => (
        <div
          key={`${dialogue.tick}-${idx}`}
          style={{
            background: '#1a1a2e',
            border: '1px solid #3a3a5e',
            borderRadius: '12px',
            padding: '10px 14px',
            maxWidth: '280px',
            opacity: 1 - (idx * 0.2), // 越早的越淡
            transition: 'opacity 0.3s',
            boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
          }}
        >
          <div style={{ fontSize: '11px', color: '#00d4ff', marginBottom: '4px', fontWeight: 'bold' }}>
            {dialogue.from}
            {dialogue.to && <span style={{ color: '#666' }}> → {dialogue.to}</span>}
          </div>
          <div style={{ fontSize: '13px', color: '#e0e0e0', lineHeight: '1.4' }}>
            {dialogue.utterance.length > 80
              ? dialogue.utterance.substring(0, 80) + '...'
              : dialogue.utterance}
          </div>
          <div style={{ fontSize: '10px', color: '#444', marginTop: '4px', textAlign: 'right' }}>
            #{dialogue.tick}
          </div>
        </div>
      ))}
    </div>
  )
}

export default DialogueBubble
/**
 * Worldsmith.tsx — V0.7 世界工坊
 * 基于自然语言的世界与角色批量生成
 */

import { useState, useCallback } from 'react'
import { storage } from '../utils/storage'

interface Location {
  id: string
  name: string
  description: string
  tags: string[]
  capacity: number
}

interface BigFive {
  openness: number
  conscientiousness: number
  extraversion: number
  agreeableness: number
  neuroticism: number
}

interface Character {
  id: string
  name: string
  age: number
  gender: string
  pronouns: string
  personality: BigFive
  identity_tags: { primary: string; secondary: string[]; self_identity: string }
  backstory: { title: string; childhood: string; adolescence: string; adulthood: string; present: string }
  initial_location: string
  introduce_text: string
  needs: { name: string; level: number }[]
  extended_personality?: Record<string, number>
}

interface Relationship {
  from_id: string
  to_id: string
  relationship_type: string
  strength: number
  shared_history: string
  potential_conflicts: string[]
}

interface WorldData {
  name: string
  description: string
  locations: Location[]
  time_rules: { day_start_hour: number; day_end_hour: number; tick_interval_minutes: number }
  atmosphere: { mood: string; dominant_themes: string[]; ambient_sounds: string[] }
}

interface PersonalityTip {
  from: string
  to: string
  type: '互补' | '冲突' | '中性'
  reason: string
}

const API_BASE = 'http://localhost:8000'

// Big Five 雷达图组件
function BigFiveRadar({ personality, size = 120 }: { personality: BigFive; size?: number }) {
  const traits = ['openness', 'conscientiousness', 'extraversion', 'agreeableness', 'neuroticism']
  const labels = ['O', 'C', 'E', 'A', 'N']
  const center = size / 2
  const radius = size / 2 - 10

  const points = traits.map((trait, i) => {
    const angle = (i * 72 - 90) * (Math.PI / 180)
    const value = personality[trait as keyof BigFive]
    const r = radius * value
    return {
      x: center + r * Math.cos(angle),
      y: center + r * Math.sin(angle),
    }
  })

  const polygonPoints = points.map(p => `${p.x},${p.y}`).join(' ')

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      {/* 背景五边形 */}
      {[0.2, 0.4, 0.6, 0.8, 1.0].map((scale, i) => {
        const pts = traits.map((_, j) => {
          const angle = (j * 72 - 90) * (Math.PI / 180)
          const r = radius * scale
          return `${center + r * Math.cos(angle)},${center + r * Math.sin(angle)}`
        }).join(' ')
        return <polygon key={i} points={pts} fill="none" stroke="var(--border-default)" strokeWidth="0.5" />
      })}
      {/* 轴线 */}
      {traits.map((_, i) => {
        const angle = (i * 72 - 90) * (Math.PI / 180)
        return (
          <line
            key={i}
            x1={center} y1={center}
            x2={center + radius * Math.cos(angle)}
            y2={center + radius * Math.sin(angle)}
            stroke="var(--border-default)" strokeWidth="0.5"
          />
        )
      })}
      {/* 数据多边形 */}
      <polygon points={polygonPoints} fill="rgba(0, 212, 255, 0.3)" stroke="var(--accent-cyan)" strokeWidth="1.5" />
      {/* 顶点标签 */}
      {traits.map((trait, i) => {
        const angle = (i * 72 - 90) * (Math.PI / 180)
        const labelPos = radius + 12
        const x = center + labelPos * Math.cos(angle)
        const y = center + labelPos * Math.sin(angle)
        return (
          <text
            key={trait}
            x={x} y={y}
            textAnchor="middle"
            dominantBaseline="middle"
            fontSize="9"
            fill="var(--text-secondary)"
          >
            {labels[i]}:{personality[trait as keyof BigFive].toFixed(1)}
          </text>
        )
      })}
    </svg>
  )
}

// 关系图组件
function RelationshipGraph({
  characters,
  relationships
}: {
  characters: Character[]
  relationships: Relationship[]
}) {
  if (!characters.length) return null

  const size = 400
  const center = size / 2
  const radius = size / 2 - 60

  const charPositions = characters.map((char, i) => {
    const angle = (i * 360 / characters.length - 90) * (Math.PI / 180)
    return {
      char,
      x: center + radius * Math.cos(angle),
      y: center + radius * Math.sin(angle),
    }
  })

  const getStrengthColor = (s: number) => {
    if (s > 0.5) return 'var(--accent-green)'
    if (s > 0) return '#86efac'
    if (s < -0.5) return 'var(--accent-red)'
    if (s < 0) return '#fca5a5'
    return 'var(--text-secondary)'
  }

  return (
    <div style={{ background: 'var(--bg-secondary)', borderRadius: 'var(--border-radius)', padding: '16px' }}>
      <h3 style={{ fontSize: '14px', color: 'var(--accent-cyan)', margin: '0 0 12px 0' }}>🔗 关系图谱</h3>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        {/* 关系连线 */}
        {relationships.map((rel, i) => {
          const from = charPositions.find(c => c.char.id === rel.from_id)
          const to = charPositions.find(c => c.char.id === rel.to_id)
          if (!from || !to) return null
          const midX = (from.x + to.x) / 2
          const midY = (from.y + to.y) / 2
          return (
            <g key={i}>
              <line
                x1={from.x} y1={from.y}
                x2={to.x} y2={to.y}
                stroke={getStrengthColor(rel.strength)}
                strokeWidth={Math.abs(rel.strength) * 3 + 1}
                opacity={0.7}
              />
              <text x={midX} y={midY} textAnchor="middle" fill="#aaa" fontSize="10">
                {rel.relationship_type} ({rel.strength.toFixed(2)})
              </text>
            </g>
          )
        })}
        {/* 角色节点 */}
        {charPositions.map(({ char, x, y }) => (
          <g key={char.id}>
            <circle cx={x} cy={y} r="25" fill="var(--bg-tertiary)" stroke="var(--accent-cyan)" strokeWidth="2" />
            <text x={x} y={y + 4} textAnchor="middle" fill="var(--accent-cyan)" fontSize="12" fontWeight="bold">
              {char.name[0]}
            </text>
            <text x={x} y={y + 40} textAnchor="middle" fill="var(--text-secondary)" fontSize="10">
              {char.name}
            </text>
          </g>
        ))}
      </svg>
    </div>
  )
}

// 角色卡片
function CharacterCard({ character, onRemove }: { character: Character; onRemove?: () => void }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div
      style={{
        background: 'var(--bg-secondary)',
        borderRadius: 'var(--border-radius)',
        padding: '16px',
        border: '1px solid var(--border-default)',
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
      }}
    >
      {/* 头部 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <div
          style={{
            width: '48px',
            height: '48px',
            borderRadius: '50%',
            background: 'linear-gradient(135deg, var(--accent-cyan), #0099cc)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '20px',
            fontWeight: 'bold',
            color: '#fff',
          }}
        >
          {character.name[0]}
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 'bold', fontSize: '16px', color: 'var(--text-primary)' }}>{character.name}</div>
          <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
            {character.age}岁 · {character.gender} · {character.identity_tags.primary}
          </div>
        </div>
        {onRemove && (
          <button
            onClick={onRemove}
            style={{
              padding: '4px 8px',
              borderRadius: '4px',
              border: 'none',
              background: 'var(--accent-red)',
              color: '#fff',
              cursor: 'pointer',
              fontSize: '11px',
            }}
          >
            移除
          </button>
        )}
      </div>

      {/* 自我介绍 */}
      {character.introduce_text && (
        <div
          style={{
            background: 'var(--bg-tertiary)',
            borderRadius: '8px',
            padding: '10px 12px',
            fontSize: '13px',
            color: '#ccc',
            fontStyle: 'italic',
            borderLeft: '3px solid var(--accent-cyan)',
          }}
        >
          "{character.introduce_text}"
        </div>
      )}

      {/* Big Five 雷达图 */}
      <div style={{ display: 'flex', justifyContent: 'center' }}>
        <BigFiveRadar personality={character.personality} size={140} />
      </div>

      {/* 扩展性格 */}
      {expanded && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '4px' }}>🎭 扩展性格</div>
          <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
            {[
              { key: 'empathy', label: '共情' },
              { key: 'humor', label: '幽默' },
              { key: 'ambition', label: '野心' },
              { key: 'loyalty', label: '忠诚' },
              { key: 'courage', label: '勇气' },
              { key: 'patience', label: '耐心' },
              { key: 'generosity', label: '慷慨' },
            ].map(({ key, label }) => {
              const val = character.extended_personality?.[key] ?? 0.5
              return (
                <span
                  key={key}
                  style={{
                    background: 'var(--bg-tertiary)',
                    padding: '2px 8px',
                    borderRadius: '4px',
                    fontSize: '11px',
                    color: '#aaa',
                  }}
                >
                  {label}: {val.toFixed(2)}
                </span>
              )
            })}
          </div>

          {/* 小传 */}
          {character.backstory && (
            <div style={{ marginTop: '8px' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '4px' }}>📖 人物小传</div>
              {character.backstory.title && (
                <div style={{ fontSize: '12px', color: 'var(--accent-yellow)', fontWeight: 'bold', marginBottom: '4px' }}>
                  {character.backstory.title}
                </div>
              )}
              {character.backstory.present && (
                <div style={{ fontSize: '12px', color: '#ccc' }}>{character.backstory.present}</div>
              )}
            </div>
          )}

          {/* 需求 */}
          {character.needs?.length > 0 && (
            <div style={{ marginTop: '8px' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '4px' }}>❤️ 初始需求</div>
              <div style={{ display: 'flex', gap: '8px', fontSize: '12px' }}>
                {character.needs.map((n, i) => (
                  <span key={i} style={{ color: '#aaa' }}>
                    {n.name}: <span style={{ color: 'var(--accent-green)' }}>{n.level.toFixed(2)}</span>
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      <button
        onClick={() => setExpanded(!expanded)}
        style={{
          padding: '6px',
          borderRadius: '6px',
          border: '1px solid var(--border-default)',
          background: 'transparent',
          color: 'var(--text-secondary)',
          cursor: 'pointer',
          fontSize: '12px',
        }}
      >
        {expanded ? '收起详情' : '展开详情'}
      </button>
    </div>
  )
}

interface WorldsmithProps {
  onApplyToEngine?: (data: { world: WorldData; characters: Character[]; relationships: Relationship[] }) => void
}

export default function Worldsmith({ onApplyToEngine }: WorldsmithProps) {
  const [description, setDescription] = useState('')
  const [numCharacters, setNumCharacters] = useState(3)
  const [model, setModel] = useState('auto')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [world, setWorld] = useState<WorldData | null>(() => storage.get<WorldData>('worldsmith_world'))
  const [characters, setCharacters] = useState<Character[]>(() => storage.get<Character[]>('worldsmith_characters') || [])
  const [relationships, setRelationships] = useState<Relationship[]>(() => storage.get<Relationship[]>('worldsmith_relationships') || [])
  const [tips, setTips] = useState<PersonalityTip[]>(() => storage.get<PersonalityTip[]>('worldsmith_tips') || [])
  const [hasGenerated, setHasGenerated] = useState(() => storage.get<WorldData>('worldsmith_world') !== null)

  // 已生成世界列表（localStorage 持久化）
  const [savedWorlds, setSavedWorlds] = useState<{ name: string; date: string; description: string }[]>(() => {
    return storage.get<{ name: string; date: string; description: string }[]>('worldsmith_saved_worlds', { persistent: true }) || []
  })

  // 保存状态到 sessionStorage（必须在 handleLoadFromList 之前定义）
  const saveToStorage = useCallback((w: WorldData | null, chars: Character[], rels: Relationship[], t: PersonalityTip[]) => {
    if (w) storage.set('worldsmith_world', w)
    else storage.remove('worldsmith_world')
    if (chars.length) storage.set('worldsmith_characters', chars)
    else storage.remove('worldsmith_characters')
    if (rels.length) storage.set('worldsmith_relationships', rels)
    else storage.remove('worldsmith_relationships')
    if (t.length) storage.set('worldsmith_tips', t)
    else storage.remove('worldsmith_tips')
  }, [])

  // 保存世界到列表
  const saveWorldToList = useCallback((w: WorldData) => {
    const entry = { name: w.name, date: new Date().toISOString(), description: w.description }
    setSavedWorlds(prev => {
      const filtered = prev.filter(x => x.name !== w.name)
      const updated = [entry, ...filtered].slice(0, 10)
      storage.set('worldsmith_saved_worlds', updated, { persistent: true })
      return updated
    })
  }, [])

  // 加载世界列表中的世界
  const handleLoadFromList = useCallback((entry: { name: string; date: string; description: string }) => {
    const keys = storage.listKeys().filter(k => k.startsWith('worldsmith_'))
    for (const key of keys) {
      try {
        const data = storage.get<any>(key)
        if (data) {
          const parsed = JSON.parse(data)
          if (parsed.world?.name === entry.name) {
            setWorld(parsed.world)
            setCharacters(parsed.characters || [])
            setRelationships(parsed.relationships || [])
            setTips(parsed.personality_tips || [])
            setHasGenerated(true)
            setDescription(parsed.world.description || '')
            saveToStorage(parsed.world, parsed.characters || [], parsed.relationships || [], parsed.personality_tips || [])
            return
          }
        }
      } catch {}
    }
    alert('未找到该世界的缓存数据，请使用"导入"功能加载之前保存的 JSON 文件')
  }, [saveToStorage])

  const handleDeleteFromList = useCallback((name: string) => {
    setSavedWorlds(prev => {
      const updated = prev.filter(x => x.name !== name)
      storage.set('worldsmith_saved_worlds', updated, { persistent: true })
      return updated
    })
  }, [])

  const handleClear = useCallback(() => {
    if (world || characters.length > 0) {
      const ok = window.confirm('清空会丢弃当前世界与所有角色，确定要继续吗？')
      if (!ok) return
    }
    setWorld(null)
    setCharacters([])
    setRelationships([])
    setTips([])
    setHasGenerated(false)
    setDescription('')
    setError(null)
    // 清除 sessionStorage
    storage.remove('worldsmith_world')
    storage.remove('worldsmith_characters')
    storage.remove('worldsmith_relationships')
    storage.remove('worldsmith_tips')
  }, [world, characters.length])

  const handleSave = useCallback(() => {
    if (!world || characters.length === 0) return

    const exportData = {
      world,
      characters,
      relationships,
      exportedAt: new Date().toISOString(),
    }

    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${world.name.replace(/\s+/g, '_')}_${Date.now()}.json`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)

    // 保存到世界列表
    saveWorldToList(world)
  }, [world, characters, relationships, saveWorldToList])

  const handleLoad = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    const reader = new FileReader()
    reader.onload = (e) => {
      try {
        const data = JSON.parse(e.target?.result as string)
        if (data.world && data.characters) {
          setWorld(data.world)
          setCharacters(data.characters)
          setRelationships(data.relationships || [])
          setTips(data.personality_tips || [])
          setHasGenerated(true)
          setDescription(data.world.description || '')
          // 保存到 sessionStorage
          saveToStorage(data.world, data.characters, data.relationships || [], data.personality_tips || [])
        }
      } catch (err) {
        setError('导入失败：文件格式错误')
      }
    }
    reader.readAsText(file)
  }, [saveToStorage])

  const handleGenerate = useCallback(async () => {
    if (!description.trim()) {
      setError('请输入世界描述')
      return
    }

    // 生成前清空之前的状态
    setWorld(null)
    setCharacters([])
    setRelationships([])
    setTips([])
    setHasGenerated(false)
    setError(null)

    setLoading(true)

    // 超时检测（300秒，与后端 Ollama 超时一致）
    const timeoutId = setTimeout(() => {
      setLoading(false)
      setError('生成超时，请检查 LLM 模型是否可用')
    }, 300000)

    try {
      const response = await fetch(`${API_BASE}/world/generate_full`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ description, num_characters: numCharacters, model }),
      })

      clearTimeout(timeoutId)

      if (!response.ok) {
        const text = await response.text()
        throw new Error(`生成失败: ${response.status}, ${text}`)
      }

      const data = await response.json()
      console.log('[Worldsmith] Generation response:', data)

      if (data.error) {
        throw new Error(data.error)
      }

      console.log('[Worldsmith] Setting world state:', !!data.world, data.world?.name)
      setWorld(data.world)
      console.log('[Worldsmith] Setting characters:', data.characters?.length)
      setCharacters(data.characters)
      console.log('[Worldsmith] Setting relationships:', data.relationships?.length)
      setRelationships(data.relationships || [])
      console.log('[Worldsmith] Setting tips:', data.personality_tips?.length)
      setTips(data.personality_tips || [])

      // 保存到 sessionStorage
      console.log('[Worldsmith] Saving to storage...')
      saveToStorage(data.world, data.characters, data.relationships || [], data.personality_tips || [])
      console.log('[Worldsmith] Done')
    } catch (e: any) {
      console.error('[Worldsmith] Generation error:', e)
      setError(e.message || '生成过程中出现错误')
    } finally {
      setLoading(false)
    }
  }, [description, numCharacters, model, saveToStorage])

  const handleApplyToEngine = useCallback(async () => {
    if (!world || characters.length === 0) return

    try {
      const response = await fetch(`${API_BASE}/world/apply`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ world, characters, relationships }),
      })
      if (response.ok) {
        const data = await response.json()
        alert(`✅ ${data.message}`)
        onApplyToEngine?.({ world, characters, relationships })
      } else {
        throw new Error(`应用失败: ${response.status}`)
      }
    } catch (e: any) {
      alert(`❌ 应用失败: ${e.message}`)
    }
  }, [world, characters, relationships, onApplyToEngine])

  return (
    <div className="worldsmith-view" style={{ padding: '20px', margin: '0 auto', width: '100%', height: '100%', display: 'flex', flexDirection: 'column', gap: '16px', boxSizing: 'border-box', overflow: 'auto' }}>
      {/* 顶栏 */}
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <h1 style={{ fontSize: '24px', color: 'var(--accent-cyan)', margin: 0 }}>
            🔨 世界工坊 <span style={{ fontSize: '14px', color: 'var(--text-muted)' }}>V0.4</span>
          </h1>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <label
            style={{
              padding: '6px 12px',
              borderRadius: '6px',
              border: '1px solid var(--border-default)',
              background: 'transparent',
              color: 'var(--text-secondary)',
              cursor: 'pointer',
              fontSize: '12px',
            }}
          >
            📂 导入
            <input
              type="file"
              accept=".json"
              onChange={handleLoad}
              style={{ display: 'none' }}
            />
          </label>
          <button
            onClick={handleSave}
            disabled={!world}
            style={{
              padding: '6px 12px',
              borderRadius: '6px',
              border: '1px solid var(--border-default)',
              background: 'transparent',
              color: world ? 'var(--text-secondary)' : 'var(--text-muted)',
              cursor: world ? 'pointer' : 'not-allowed',
              fontSize: '12px',
            }}
          >
            💾 导出
          </button>
          <button
            onClick={handleApplyToEngine}
            disabled={!world}
            style={{
              padding: '8px 16px',
              borderRadius: '6px',
              border: 'none',
              background: world ? 'var(--accent-green)' : 'var(--bg-tertiary)',
              color: world ? '#000' : 'var(--text-muted)',
              fontWeight: 'bold',
              cursor: world ? 'pointer' : 'not-allowed',
              fontSize: '13px',
            }}
          >
            ✅ 应用到引擎
          </button>
          <button
            onClick={handleClear}
            style={{
              padding: '6px 12px',
              borderRadius: 'var(--border-radius-sm)',
              border: '1px solid var(--border-default)',
              background: 'transparent',
              color: 'var(--text-secondary)',
              cursor: 'pointer',
              fontSize: '12px',
            }}
          >
            🗑️ 清空
          </button>
        </div>
      </header>

      {/* 生成表单 */}
      <div style={{ background: 'var(--bg-secondary)', borderRadius: 'var(--border-radius)', padding: '16px', flexShrink: 0 }}>
        <h2 style={{ fontSize: '14px', color: 'var(--accent-cyan)', margin: '0 0 12px 0' }}>🎲 生成新世界</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div style={{ width: '100%' }}>
            <label style={{ fontSize: '12px', color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>
              世界描述
            </label>
            <textarea
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="例如：一个中世纪风格的小镇，有图书馆、面包店、广场酒馆..."
              style={{
                width: '100%',
                height: '120px',
                padding: '10px',
                borderRadius: '8px',
                border: '1px solid var(--border-default)',
                background: 'var(--bg-primary)',
                color: '#fff',
                fontSize: '14px',
                resize: 'vertical',
              }}
            />
          </div>
          <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-end' }}>
            <div>
              <label style={{ fontSize: '12px', color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>
                LLM 模型
              </label>
              <select
                value={model}
                onChange={e => setModel(e.target.value)}
                style={{
                  padding: '10px',
                  borderRadius: '8px',
                  border: '1px solid var(--border-default)',
                  background: 'var(--bg-primary)',
                  color: '#fff',
                  fontSize: '14px',
                }}
              >
                <option value="auto">自动（本地优先）</option>
                <option value="local">本地 Ollama</option>
                <option value="cloud">云端 MiniMax</option>
              </select>
            </div>
            <div>
              <label style={{ fontSize: '12px', color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>
                角色数量
              </label>
              <select
                value={numCharacters}
                onChange={e => setNumCharacters(Number(e.target.value))}
                style={{
                  padding: '10px',
                  borderRadius: '8px',
                  border: '1px solid var(--border-default)',
                  background: 'var(--bg-primary)',
                  color: '#fff',
                  fontSize: '14px',
                }}
              >
                {[2, 3, 4, 5, 6, 7, 8, 9, 10].map(n => (
                  <option key={n} value={n}>{n}</option>
                ))}
              </select>
            </div>
            <button
              onClick={handleGenerate}
              disabled={loading}
              style={{
                padding: '12px 24px',
                borderRadius: '8px',
                border: 'none',
                background: loading ? 'var(--bg-tertiary)' : 'var(--accent-cyan)',
                color: loading ? 'var(--text-muted)' : '#000',
                fontWeight: 'bold',
                cursor: loading ? 'not-allowed' : 'pointer',
                fontSize: '14px',
              }}
            >
              {loading ? '生成中...' : '🚀 开始生成'}
            </button>
          </div>
        </div>
        {error && (
          <div style={{ marginTop: '8px', fontSize: '12px', color: 'var(--accent-red)' }}>
            ⚠️ {error}
          </div>
        )}
      </div>

      {/* 主内容区 */}
      {world && characters.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: '16px', flex: 1, minHeight: 0, overflow: 'auto' }}>
          {/* 左：角色卡片 */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', overflow: 'auto' }}>
            {/* 世界信息 */}
            <div style={{ background: 'var(--bg-secondary)', borderRadius: 'var(--border-radius)', padding: '16px' }}>
              <h2 style={{ fontSize: '16px', color: 'var(--accent-cyan)', margin: '0 0 8px 0' }}>🌍 {world.name}</h2>
              <p style={{ fontSize: '13px', color: 'var(--text-secondary)', margin: '0 0 12px 0' }}>{world.description}</p>
              <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', fontSize: '12px' }}>
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>地点:</span>{' '}
                  {world.locations.map(l => l.name).join(', ')}
                </div>
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>氛围:</span>{' '}
                  {world.atmosphere.mood}
                </div>
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>时间:</span>{' '}
                  {world.time_rules.day_start_hour}:00 - {world.time_rules.day_end_hour}:00
                </div>
              </div>
            </div>

            {/* 性格提示 */}
            {tips.length > 0 && (
              <div style={{ background: 'var(--bg-secondary)', borderRadius: 'var(--border-radius)', padding: '16px' }}>
                <h3 style={{ fontSize: '14px', color: 'var(--accent-yellow)', margin: '0 0 8px 0' }}>💡 性格互动提示</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  {tips.map((tip, i) => (
                    <div key={i} style={{ fontSize: '12px', color: '#ccc' }}>
                      <span style={{
                        padding: '2px 6px',
                        borderRadius: '4px',
                        background: tip.type === '互补' ? 'var(--accent-green)' : tip.type === '冲突' ? 'var(--accent-red)' : 'var(--text-secondary)',
                        color: '#000',
                        fontSize: '10px',
                        marginRight: '6px',
                      }}>
                        {tip.type}
                      </span>
                      <span style={{ color: 'var(--accent-cyan)' }}>{tip.from}</span>
                      <span style={{ color: 'var(--text-muted)' }}> → </span>
                      <span style={{ color: 'var(--accent-cyan)' }}>{tip.to}</span>
                      <span style={{ color: 'var(--text-secondary)' }}>: {tip.reason}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 角色卡片 */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '16px' }}>
              {characters.map((char, i) => (
                <CharacterCard key={char.id || i} character={char} />
              ))}
            </div>
          </div>

          {/* 右：关系图谱 */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', overflow: 'auto' }}>
            <RelationshipGraph characters={characters} relationships={relationships} />

            {/* 地点列表 */}
            {world.locations.length > 0 && (
              <div style={{ background: 'var(--bg-secondary)', borderRadius: 'var(--border-radius)', padding: '16px' }}>
                <h3 style={{ fontSize: '14px', color: 'var(--accent-cyan)', margin: '0 0 12px 0' }}>📍 地点列表</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {world.locations.map(loc => (
                    <div key={loc.id} style={{ background: 'var(--bg-tertiary)', borderRadius: '8px', padding: '10px' }}>
                      <div style={{ fontWeight: 'bold', fontSize: '13px', color: 'var(--text-primary)' }}>{loc.name}</div>
                      <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>{loc.description}</div>
                      <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '4px' }}>
                        {loc.tags.join(', ')} · 容量 {loc.capacity}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 已生成世界列表 */}
      {savedWorlds.length > 0 && (
        <div style={{ background: 'var(--bg-secondary)', borderRadius: 'var(--border-radius)', padding: '16px', flexShrink: 0 }}>
          <h3 style={{ fontSize: '14px', color: 'var(--accent-cyan)', margin: '0 0 8px 0' }}>📚 已生成世界</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', maxHeight: '160px', overflow: 'auto' }}>
            {savedWorlds.map((w, i) => (
              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--bg-tertiary)', borderRadius: '8px', padding: '8px 12px' }}>
                <div style={{ flex: 1, cursor: 'pointer' }} onClick={() => handleLoadFromList(w)}>
                  <div style={{ fontSize: '13px', color: 'var(--text-primary)', fontWeight: 'bold' }}>{w.name}</div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{new Date(w.date).toLocaleDateString()} · {w.description?.slice(0, 30)}...</div>
                </div>
                <button
                  onClick={() => handleDeleteFromList(w.name)}
                  style={{ padding: '4px 8px', borderRadius: '4px', border: 'none', background: 'var(--accent-red)', color: '#fff', cursor: 'pointer', fontSize: '10px', marginLeft: '8px' }}
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 空状态 */}
      {!world && !loading && (
        <div style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'var(--text-muted)',
          fontSize: '14px',
        }}>
          <div style={{ fontSize: '48px', marginBottom: '16px' }}>🔨</div>
          <div>在上方输入世界描述，开始生成你的世界</div>
        </div>
      )}
    </div>
  )
}
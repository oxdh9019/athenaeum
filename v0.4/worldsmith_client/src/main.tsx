import { useState, useCallback, useEffect } from 'react'
import { createRoot } from 'react-dom/client'

/**
 * Worldsmith.jsx — V0.4 世界工坊前端
 * 基于自然语言的世界与角色批量生成 + Web 审核界面
 */

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

interface GenerationMetrics {
  cloud_tokens_input: number
  cloud_tokens_output: number
  cloud_cost: number
  cloud_call_count: number
  local_call_count: number
}

interface PersonalityTip {
  from: string
  to: string
  type: '互补' | '冲突' | '中性'
  reason: string
}

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
        return <polygon key={i} points={pts} fill="none" stroke="#333" strokeWidth="0.5" />
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
            stroke="#333" strokeWidth="0.5"
          />
        )
      })}
      {/* 数据多边形 */}
      <polygon points={polygonPoints} fill="rgba(0, 212, 255, 0.3)" stroke="#00d4ff" strokeWidth="1.5" />
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
            fill="#888"
          >
            {labels[i]}:{personality[trait as keyof BigFive].toFixed(1)}
          </text>
        )
      })}
    </svg>
  )
}

// 关系图组件（简化版）
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
    if (s > 0.5) return '#4ade80'
    if (s > 0) return '#86efac'
    if (s < -0.5) return '#ef4444'
    if (s < 0) return '#fca5a5'
    return '#888'
  }

  return (
    <div style={{ background: '#1a1a2e', borderRadius: '12px', padding: '16px' }}>
      <h3 style={{ fontSize: '14px', color: '#00d4ff', margin: '0 0 12px 0' }}>🔗 关系图谱</h3>
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
            <circle cx={x} cy={y} r="25" fill="#2a2a4e" stroke="#00d4ff" strokeWidth="2" />
            <text x={x} y={y + 4} textAnchor="middle" fill="#00d4ff" fontSize="12" fontWeight="bold">
              {char.name[0]}
            </text>
            <text x={x} y={y + 40} textAnchor="middle" fill="#888" fontSize="10">
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
        background: '#1a1a2e',
        borderRadius: '12px',
        padding: '16px',
        border: '1px solid #333',
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
            background: 'linear-gradient(135deg, #00d4ff, #0099cc)',
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
          <div style={{ fontWeight: 'bold', fontSize: '16px', color: '#fff' }}>{character.name}</div>
          <div style={{ fontSize: '12px', color: '#888' }}>
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
              background: '#ef4444',
              color: '#fff',
              cursor: 'pointer',
              fontSize: '11px',
            }}
          >
            移除
          </button>
        )}
      </div>

      {/* 自我介绍（本地 Qwen 生成） */}
      {character.introduce_text && (
        <div
          style={{
            background: '#2a2a4e',
            borderRadius: '8px',
            padding: '10px 12px',
            fontSize: '13px',
            color: '#ccc',
            fontStyle: 'italic',
            borderLeft: '3px solid #00d4ff',
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
          <div style={{ fontSize: '11px', color: '#666', marginBottom: '4px' }}>🎭 扩展性格</div>
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
              const val = (character as any).extended_personality?.[key] ?? 0.5
              return (
                <span
                  key={key}
                  style={{
                    background: '#2a2a4e',
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
              <div style={{ fontSize: '11px', color: '#666', marginBottom: '4px' }}>📖 人物小传</div>
              {character.backstory.title && (
                <div style={{ fontSize: '12px', color: '#f59e0b', fontWeight: 'bold', marginBottom: '4px' }}>
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
              <div style={{ fontSize: '11px', color: '#666', marginBottom: '4px' }}>❤️ 初始需求</div>
              <div style={{ display: 'flex', gap: '8px', fontSize: '12px' }}>
                {character.needs.map((n, i) => (
                  <span key={i} style={{ color: '#aaa' }}>
                    {n.name}: <span style={{ color: '#4ade80' }}>{n.level.toFixed(2)}</span>
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
          border: '1px solid #444',
          background: 'transparent',
          color: '#888',
          cursor: 'pointer',
          fontSize: '12px',
        }}
      >
        {expanded ? '收起详情' : '展开详情'}
      </button>
    </div>
  )
}

export default function Worldsmith() {
  const [description, setDescription] = useState('')
  const [numCharacters, setNumCharacters] = useState(3)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [disableAutoSave, setDisableAutoSave] = useState(false)

  const [world, setWorld] = useState<WorldData | null>(null)
  const [characters, setCharacters] = useState<Character[]>([])
  const [relationships, setRelationships] = useState<Relationship[]>([])
  const [tips, setTips] = useState<PersonalityTip[]>([])
  const [metrics, setMetrics] = useState<GenerationMetrics | null>(null)

  useEffect(() => {
    const saved = localStorage.getItem('worldsmith_data')
    if (saved) {
      try {
        const data = JSON.parse(saved)
        if (data.world) setWorld(data.world)
        if (data.characters) setCharacters(data.characters)
        if (data.relationships) setRelationships(data.relationships)
        if (data.tips) setTips(data.tips)
        if (data.metrics) setMetrics(data.metrics)
        if (data.description) setDescription(data.description)
        if (data.numCharacters) setNumCharacters(data.numCharacters)
      } catch (e) {
        console.error('Failed to load saved data:', e)
      }
    }
  }, [])

  useEffect(() => {
    if (disableAutoSave) return
    
    const data = {
      world,
      characters,
      relationships,
      tips,
      metrics,
      description,
      numCharacters,
    }
    localStorage.setItem('worldsmith_data', JSON.stringify(data))
  }, [world, characters, relationships, tips, metrics, description, numCharacters, disableAutoSave])

  const handleGenerate = useCallback(async () => {
    if (!description.trim()) {
      setError('请输入世界描述')
      return
    }

    setLoading(true)
    setError(null)
    setDisableAutoSave(true)  // 禁用自动保存
    localStorage.removeItem('worldsmith_data')

    try {
      const response = await fetch('/world/generate_full', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ description, num_characters: numCharacters }),
      })

      if (!response.ok) {
        throw new Error(`生成失败: ${response.status}`)
      }

      const data = await response.json()

      setWorld(data.world)
      setCharacters(data.characters)
      setRelationships(data.relationships)
      setTips(data.personality_tips || [])
      setMetrics(data.metrics)
      
      // 先手动保存，然后再启用自动保存
      const saveData = {
        world: data.world,
        characters: data.characters,
        relationships: data.relationships,
        tips: data.personality_tips || [],
        metrics: data.metrics,
        description,
        numCharacters,
      }
      localStorage.setItem('worldsmith_data', JSON.stringify(saveData))
    } catch (e: any) {
      setError(e.message || '生成过程中出现错误')
    } finally {
      setLoading(false)
      setDisableAutoSave(false)  // 重新启用自动保存
    }
  }, [description, numCharacters])

  const handleRegenerateIntro = useCallback(async (charId: string) => {
    // 重新生成单个角色的 introduce_text
    const char = characters.find(c => c.id === charId)
    if (!char) return

    try {
      const response = await fetch(`/characters/${charId}/introduce_text?characters=${encodeURIComponent(JSON.stringify(characters))}`)
      if (response.ok) {
        const data = await response.json()
        setCharacters(prev =>
          prev.map(c => c.id === charId ? { ...c, introduce_text: data.introduce_text } : c)
        )
      }
    } catch (e) {
      console.error('Regenerate intro failed:', e)
    }
  }, [characters])

  const handleApplyToEngine = useCallback(async () => {
    if (!world || characters.length === 0) return

    try {
      const response = await fetch('/world/apply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ world, characters }),
      })
      if (response.ok) {
        const data = await response.json()
        console.log('✅ 引擎已启动:', data.message)
        // 引擎启动成功，不阻塞 UI，用户可自行切换到主页查看
      } else {
        throw new Error(`应用失败: ${response.status}`)
      }
    } catch (e: any) {
      console.error('❌ 应用失败:', e.message)
      // 显示错误但不阻塞
      setError(`应用失败: ${e.message}`)
    }
  }, [world, characters])

  return (
    <div style={{ padding: '20px', margin: '0 auto', width: '100%', height: '100%', display: 'flex', flexDirection: 'column', gap: '16px', boxSizing: 'border-box' }}>
      {/* 顶栏 */}
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <h1 style={{ fontSize: '24px', color: '#00d4ff', margin: 0 }}>
            🔨 世界工坊 <span style={{ fontSize: '14px', color: '#666' }}>V0.4</span>
          </h1>
        </div>
        {metrics && (
          <div style={{ fontSize: '11px', color: '#666', display: 'flex', gap: '16px' }}>
            <span>☁️ 云端调用: {metrics.cloud_call_count}次</span>
            <span>💻 本地调用: {metrics.local_call_count}次</span>
            <span>💰 成本: ${metrics.cloud_cost.toFixed(4)}</span>
          </div>
        )}
      </header>

      {/* 生成表单 */}
      <div style={{ background: '#1a1a2e', borderRadius: '12px', padding: '16px', flexShrink: 0 }}>
        <h2 style={{ fontSize: '14px', color: '#00d4ff', margin: '0 0 12px 0' }}>🎲 生成新世界</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div style={{ width: '100%' }}>
            <label style={{ fontSize: '12px', color: '#888', display: 'block', marginBottom: '4px' }}>
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
                border: '1px solid #444',
                background: '#0a0a1e',
                color: '#fff',
                fontSize: '14px',
                resize: 'vertical',
              }}
            />
          </div>
          <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-end' }}>
            <div>
              <label style={{ fontSize: '12px', color: '#888', display: 'block', marginBottom: '4px' }}>
                角色数量
              </label>
              <select
                value={numCharacters}
                onChange={e => setNumCharacters(Number(e.target.value))}
                style={{
                  padding: '10px',
                  borderRadius: '8px',
                  border: '1px solid #444',
                  background: '#0a0a1e',
                  color: '#fff',
                  fontSize: '14px',
                }}
              >
                {[2, 3, 4, 5, 6, 7, 8, 9, 10].map(n => (
                  <option key={n} value={n}>{n}</option>
                ))}
              </select>
            </div>
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <label
                style={{
                  padding: '12px 16px',
                  borderRadius: '8px',
                  border: '1px solid #444',
                  background: 'transparent',
                  color: '#888',
                  cursor: 'pointer',
                  fontSize: '12px',
                  display: 'inline-block',
                }}
              >
                📥 导入
                <input
                  type="file"
                  accept=".json"
                  style={{ display: 'none' }}
                  onChange={e => {
                    const file = e.target.files?.[0]
                    if (!file) return
                    const reader = new FileReader()
                    reader.onload = ev => {
                      try {
                        const data = JSON.parse(ev.target?.result as string)
                        if (data.world) setWorld(data.world)
                        if (data.characters) setCharacters(data.characters)
                        if (data.relationships) setRelationships(data.relationships)
                        if (data.tips) setTips(data.tips)
                        if (data.metrics) setMetrics(data.metrics)
                        if (data.description) setDescription(data.description)
                        alert('✅ 导入成功')
                      } catch (err) {
                        alert('❌ 导入失败：文件格式错误')
                      }
                    }
                    reader.readAsText(file)
                  }}
                />
              </label>
              <button
                onClick={handleGenerate}
                disabled={loading}
                style={{
                  padding: '12px 24px',
                  borderRadius: '8px',
                  border: 'none',
                  background: loading ? '#333' : '#00d4ff',
                  color: loading ? '#666' : '#000',
                  fontWeight: 'bold',
                  cursor: loading ? 'not-allowed' : 'pointer',
                  fontSize: '14px',
                }}
              >
                {loading ? '生成中...' : '🚀 开始生成'}
              </button>
              <button
                onClick={() => {
                  if (confirm('确定要清空所有已生成的数据吗？')) {
                    localStorage.removeItem('worldsmith_data')
                    setWorld(null)
                    setCharacters([])
                    setRelationships([])
                    setTips([])
                    setMetrics(null)
                    setDescription('')
                    setNumCharacters(3)
                    setError(null)
                  }
                }}
                style={{
                  padding: '12px 16px',
                  borderRadius: '8px',
                  border: '1px solid #444',
                  background: 'transparent',
                  color: '#888',
                  cursor: 'pointer',
                  fontSize: '12px',
                }}
              >
                🗑️ 清空
              </button>
            </div>
          </div>
        </div>
        {error && (
          <div style={{ marginTop: '8px', fontSize: '12px', color: '#ef4444' }}>
            ⚠️ {error}
          </div>
        )}
      </div>

      {/* 主内容区 */}
      {world && characters.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: '16px', flex: 1, minHeight: 0 }}>
          {/* 左：角色卡片 */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', overflow: 'auto' }}>
            {/* 世界信息 */}
            <div style={{ background: '#1a1a2e', borderRadius: '12px', padding: '16px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <h2 style={{ fontSize: '16px', color: '#00d4ff', margin: 0 }}>🌍 {world.name}</h2>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    onClick={() => {
                      const exportData = {
                        version: '0.4',
                        exported_at: new Date().toISOString(),
                        world,
                        characters,
                        relationships,
                        tips,
                      }
                      const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' })
                      const url = URL.createObjectURL(blob)
                      const a = document.createElement('a')
                      a.href = url
                      a.download = `${world.name.replace(/\s+/g, '_')}_世界数据.json`
                      a.click()
                      URL.revokeObjectURL(url)
                    }}
                    style={{
                      padding: '8px 12px',
                      borderRadius: '6px',
                      border: '1px solid #444',
                      background: 'transparent',
                      color: '#888',
                      cursor: 'pointer',
                      fontSize: '12px',
                    }}
                  >
                    📤 导出
                  </button>
                  <label
                    style={{
                      padding: '8px 12px',
                      borderRadius: '6px',
                      border: '1px solid #444',
                      background: 'transparent',
                      color: '#888',
                      cursor: 'pointer',
                      fontSize: '12px',
                      display: 'inline-block',
                    }}
                  >
                    📥 导入
                    <input
                      type="file"
                      accept=".json"
                      style={{ display: 'none' }}
                      onChange={e => {
                        const file = e.target.files?.[0]
                        if (!file) return
                        const reader = new FileReader()
                        reader.onload = ev => {
                          try {
                            const data = JSON.parse(ev.target?.result as string)
                            if (data.world) setWorld(data.world)
                            if (data.characters) setCharacters(data.characters)
                            if (data.relationships) setRelationships(data.relationships)
                            if (data.tips) setTips(data.tips)
                            alert('✅ 导入成功')
                          } catch (err) {
                            alert('❌ 导入失败：文件格式错误')
                          }
                        }
                        reader.readAsText(file)
                      }}
                    />
                  </label>
                  <button
                    onClick={handleApplyToEngine}
                    style={{
                      padding: '8px 16px',
                      borderRadius: '6px',
                      border: 'none',
                      background: '#4ade80',
                      color: '#000',
                      fontWeight: 'bold',
                      cursor: 'pointer',
                      fontSize: '13px',
                    }}
                  >
                    ✅ 应用到引擎
                  </button>
                </div>
              </div>
              <p style={{ fontSize: '13px', color: '#888', margin: '0 0 12px 0' }}>{world.description}</p>
              <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', fontSize: '12px' }}>
                <div>
                  <span style={{ color: '#666' }}>地点:</span>{' '}
                  {world.locations.map(l => l.name).join(', ')}
                </div>
                <div>
                  <span style={{ color: '#666' }}>氛围:</span>{' '}
                  {world.atmosphere.mood}
                </div>
                <div>
                  <span style={{ color: '#666' }}>时间:</span>{' '}
                  {world.time_rules.day_start_hour}:00 - {world.time_rules.day_end_hour}:00
                </div>
              </div>
            </div>

            {/* 性格提示 */}
            {tips.length > 0 && (
              <div style={{ background: '#1a1a2e', borderRadius: '12px', padding: '16px' }}>
                <h3 style={{ fontSize: '14px', color: '#f59e0b', margin: '0 0 8px 0' }}>💡 性格互动提示</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  {tips.map((tip, i) => (
                    <div key={i} style={{ fontSize: '12px', color: '#ccc' }}>
                      <span style={{
                        padding: '2px 6px',
                        borderRadius: '4px',
                        background: tip.type === '互补' ? '#4ade80' : tip.type === '冲突' ? '#ef4444' : '#888',
                        color: '#000',
                        fontSize: '10px',
                        marginRight: '6px',
                      }}>
                        {tip.type}
                      </span>
                      <span style={{ color: '#00d4ff' }}>{tip.from}</span>
                      <span style={{ color: '#666' }}> → </span>
                      <span style={{ color: '#00d4ff' }}>{tip.to}</span>
                      <span style={{ color: '#888' }}>: {tip.reason}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 角色卡片网格 */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '16px' }}>
              {characters.map(char => (
                <CharacterCard
                  key={char.id}
                  character={char}
                  onRemove={() => setCharacters(prev => prev.filter(c => c.id !== char.id))}
                />
              ))}
            </div>
          </div>

          {/* 右：关系图谱 */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', overflow: 'auto' }}>
            <RelationshipGraph characters={characters} relationships={relationships} />

            {/* 地点列表 */}
            {world.locations.length > 0 && (
              <div style={{ background: '#1a1a2e', borderRadius: '12px', padding: '16px' }}>
                <h3 style={{ fontSize: '14px', color: '#00d4ff', margin: '0 0 12px 0' }}>📍 地点列表</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {world.locations.map(loc => (
                    <div key={loc.id} style={{ background: '#2a2a4e', borderRadius: '8px', padding: '10px' }}>
                      <div style={{ fontWeight: 'bold', fontSize: '13px', color: '#fff' }}>{loc.name}</div>
                      <div style={{ fontSize: '11px', color: '#666', marginTop: '2px' }}>{loc.description}</div>
                      <div style={{ fontSize: '10px', color: '#444', marginTop: '4px' }}>
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

      {/* 空状态 */}
      {!world && !loading && (
        <div style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#555',
          fontSize: '14px',
        }}>
          <div style={{ fontSize: '48px', marginBottom: '16px' }}>🔨</div>
          <div>在上方输入世界描述，开始生成你的世界</div>
        </div>
      )}
    </div>
  )
}

const root = createRoot(document.getElementById('root')!)
root.render(<Worldsmith />)

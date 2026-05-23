/**
 * TopBar.tsx — V0.7 世界底色栏
 * 显示时间、天气、叙事状态、路由状态
 */

interface TopBarProps {
  gameHour: number
  timeOfDay: string
  weather: string
  tickId: number
  tickType: string
  routerStats?: {
    local_calls: number
    cloud_calls: number
    budget_remaining: number
  }
}

const TIME_ICONS: Record<string, string> = {
  dawn: '🌅',
  morning: '☀️',
  noon: '🌞',
  afternoon: '🌤️',
  evening: '🌆',
  night: '🌙',
  midnight: '🌑',
}

const WEATHER_ICONS: Record<string, string> = {
  clear: '☀️',
  cloudy: '☁️',
  rainy: '🌧️',
  stormy: '⛈️',
  snowy: '❄️',
  foggy: '🌫️',
}

function TopBar({ gameHour, timeOfDay, weather, tickId, tickType, routerStats }: TopBarProps) {
  return (
    <div style={{
      height: '48px',
      background: '#1a1a2e',
      borderBottom: '1px solid #2a2a4e',
      display: 'flex',
      alignItems: 'center',
      padding: '0 16px',
      gap: '24px',
      flexShrink: 0,
    }}>
      {/* 时间 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <span style={{ fontSize: '18px', fontWeight: 'bold', color: '#e0e0e0' }}>
          {String(gameHour).padStart(2, '0')}:00
        </span>
        <span style={{ color: '#888', fontSize: '14px' }}>
          {TIME_ICONS[timeOfDay] || '⏰'} {timeOfDay}
        </span>
      </div>

      {/* 天气 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#888', fontSize: '14px' }}>
        {WEATHER_ICONS[weather] || '🌡️'} {weather}
      </div>

      {/* 分割线 */}
      <div style={{ width: '1px', height: '24px', background: '#2a2a4e' }} />

      {/* Tick 信息 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', color: '#666' }}>
        <span>Tick: <span style={{ color: '#00d4ff' }}>{tickId}</span></span>
        <span
          style={{
            padding: '2px 8px',
            borderRadius: '4px',
            fontSize: '11px',
            background: tickType === 'ACTIVE' ? '#22c55e20' : '#f59e0b20',
            color: tickType === 'ACTIVE' ? '#4ade80' : '#f59e0b',
          }}
        >
          {tickType}
        </span>
      </div>

      {/* 路由状态 */}
      {routerStats && (
        <>
          <div style={{ width: '1px', height: '24px', background: '#2a2a4e' }} />
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', fontSize: '12px', color: '#666' }}>
            <span style={{ color: '#4ade80' }}>◉ Local</span>
            <span style={{ color: '#00d4ff' }}>◯ Cloud</span>
            <span>预算: <span style={{ color: '#f59e0b' }}>{routerStats.budget_remaining.toFixed(1)}</span></span>
          </div>
        </>
      )}

      {/* 右侧：世界叙事提示（预留） */}
      <div style={{ flex: 1 }} />
      <div style={{ fontSize: '12px', color: '#555' }}>
        🌍 World Pulse V0.7
      </div>
    </div>
  )
}

export default TopBar
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
    <div className="topbar">
      {/* 时间 */}
      <div className="topbar-section">
        <span className="topbar-time">
          {String(gameHour).padStart(2, '0')}:00
        </span>
        <span className="topbar-icon">
          {TIME_ICONS[timeOfDay] || '⏰'} {timeOfDay}
        </span>
      </div>

      {/* 天气 */}
      <div className="topbar-section topbar-icon">
        {WEATHER_ICONS[weather] || '🌡️'} {weather}
      </div>

      {/* 分割线 */}
      <div className="topbar-divider" />

      {/* Tick 信息 */}
      <div className="topbar-section topbar-tick">
        Tick: <span style={{ color: 'var(--accent-cyan)' }}>{tickId}</span>
        <span
          className={`topbar-tick-type ${tickType === 'ACTIVE' ? 'tick-type-active' : 'tick-type-silent'}`}
        >
          {tickType}
        </span>
      </div>

      {/* 路由状态 */}
      {routerStats && (
        <>
          <div className="topbar-divider" />
          <div className="topbar-stats">
            <span className="local">◉ Local</span>
            <span className="cloud">◯ Cloud</span>
            <span>预算: <span className="budget">{routerStats.budget_remaining.toFixed(1)}</span></span>
          </div>
        </>
      )}

      {/* 右侧：品牌 */}
      <div className="topbar-brand">
        🌍 Athenaeum V0.7
      </div>
    </div>
  )
}

export default TopBar
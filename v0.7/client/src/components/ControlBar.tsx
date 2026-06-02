/**
 * ControlBar.tsx — V0.7 控制栏组件
 * 暂停/恢复、时间显示、连接状态、视图切换
 */

import type { ConnectionState } from '../hooks/types'

interface ControlBarProps {
  connectionState: ConnectionState
  paused: boolean
  tickId: number
  gameHour: number
  timeOfDay: string
  weather: string
  onTogglePause: () => void
  onStop: () => void
  viewMode: string
  onViewModeChange: (mode: string) => void
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

const CONNECTION_COLORS: Record<ConnectionState, string> = {
  connecting: 'var(--accent-yellow)',
  connected: 'var(--accent-green)',
  disconnected: 'var(--accent-red)',
  reconnecting: 'var(--accent-yellow)',
}

const CONNECTION_LABELS: Record<ConnectionState, string> = {
  connecting: '连接中...',
  connected: '● 已连接',
  disconnected: '○ 已断开',
  reconnecting: '⟳ 重连中...',
}

const VIEW_MODES = [
  { key: 'dashboard', label: '仪表盘', icon: '📊' },
  { key: 'agents', label: '角色', icon: '👥' },
  { key: 'dialogue', label: '对话', icon: '💬' },
  { key: 'soul', label: '灵魂', icon: '🔮' },
]

function ControlBar({
  connectionState,
  paused,
  tickId,
  gameHour,
  timeOfDay,
  weather,
  onTogglePause,
  onStop,
  viewMode,
  onViewModeChange,
}: ControlBarProps) {
  return (
    <div className="control-bar">
      {/* 左侧：时间 + 天气 + 连接状态 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '18px', fontWeight: 'bold', color: 'var(--accent-cyan)' }}>
            {String(gameHour).padStart(2, '0')}:00
          </span>
          <span style={{ fontSize: '16px' }}>
            {TIME_ICONS[timeOfDay] || '⏰'} {timeOfDay}
          </span>
          <span style={{ fontSize: '16px' }}>
            {WEATHER_ICONS[weather] || '🌡️'} {weather}
          </span>
        </div>
        <span style={{ color: 'var(--text-muted)', fontSize: '12px' }}>Tick: {tickId}</span>
        {paused && (
          <span style={{
            padding: '2px 8px',
            borderRadius: '10px',
            fontSize: '11px',
            background: 'rgba(245, 158, 11, 0.13)',
            color: 'var(--accent-yellow)',
          }}>
            ⏸️ 已暂停
          </span>
        )}
      </div>

      {/* 中间：连接状态 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <span style={{ color: CONNECTION_COLORS[connectionState], fontSize: '12px' }}>
          {CONNECTION_LABELS[connectionState]}
        </span>
      </div>

      {/* 右侧：暂停按钮 + 停止按钮 + 视图切换 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginLeft: 'auto' }}>
        <button
          onClick={onTogglePause}
          className={`control-bar-btn ${paused ? 'resume' : 'pause'}`}
        >
          {paused ? '▶️ 继续' : '⏸️ 暂停'}
        </button>

        <button
          onClick={onStop}
          style={{
            padding: '6px 16px',
            borderRadius: 'var(--border-radius-sm)',
            border: 'none',
            background: 'var(--accent-red)',
            color: '#fff',
            cursor: 'pointer',
            fontSize: '12px',
            fontWeight: 'bold',
          }}
        >
          ■ 停止
        </button>

        {/* 视图切换 */}
        <div className="control-bar-views">
          {VIEW_MODES.map(mode => (
            <button
              key={mode.key}
              onClick={() => onViewModeChange(mode.key)}
              className={`view-btn ${viewMode === mode.key ? 'active' : 'inactive'}`}
            >
              {mode.icon} {mode.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

export default ControlBar
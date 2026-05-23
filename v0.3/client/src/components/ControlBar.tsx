/**
 * ControlBar.tsx — V0.7 控制栏组件
 * 暂停/恢复、时间显示、连接状态
 */

import type { ConnectionState } from '../hooks/useWorldSocket'

interface ControlBarProps {
  connectionState: ConnectionState
  paused: boolean
  tickId: number
  gameHour: number
  timeOfDay: string
  weather: string
  onTogglePause: () => void
  onViewModeChange?: (mode: string) => void
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
  connecting: '#f59e0b',
  connected: '#4ade80',
  disconnected: '#ef4444',
  reconnecting: '#f59e0b',
}

const CONNECTION_LABELS: Record<ConnectionState, string> = {
  connecting: '连接中...',
  connected: '● 已连接',
  disconnected: '○ 已断开',
  reconnecting: '⟳ 重连中...',
}

function ControlBar({
  connectionState,
  paused,
  tickId,
  gameHour,
  timeOfDay,
  weather,
  onTogglePause,
}: ControlBarProps) {
  return (
    <header style={{
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      padding: '12px 16px',
      background: '#1a1a2e',
      borderRadius: '12px',
    }}>
      {/* 左侧：时间 + 天气 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '20px', fontWeight: 'bold', color: '#00d4ff' }}>
            {String(gameHour).padStart(2, '0')}:00
          </span>
          <span style={{ fontSize: '16px' }}>
            {TIME_ICONS[timeOfDay] || '⏰'} {timeOfDay}
          </span>
          <span style={{ fontSize: '16px' }}>
            {WEATHER_ICONS[weather] || '🌡️'} {weather}
          </span>
        </div>
        <span style={{ color: '#555', fontSize: '12px' }}>Tick: {tickId}</span>
        {paused && (
          <span style={{
            padding: '2px 8px',
            borderRadius: '10px',
            fontSize: '11px',
            background: '#f59e0b20',
            color: '#f59e0b',
          }}>
            ⏸️ 已暂停
          </span>
        )}
      </div>

      {/* 右侧：连接状态 + 暂停按钮 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <span style={{ color: CONNECTION_COLORS[connectionState], fontSize: '12px' }}>
          {CONNECTION_LABELS[connectionState]}
        </span>
        <button
          onClick={onTogglePause}
          style={{
            padding: '8px 16px',
            borderRadius: '8px',
            border: 'none',
            background: paused ? '#22c55e' : '#f59e0b',
            color: '#fff',
            cursor: 'pointer',
            fontWeight: 'bold',
            fontSize: '12px',
          }}
        >
          {paused ? '▶️ 继续' : '⏸️ 暂停'}
        </button>
      </div>
    </header>
  )
}

export default ControlBar
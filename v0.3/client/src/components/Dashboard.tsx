/**
 * Dashboard.tsx — V0.7 成本监控仪表盘
 * 显示预算使用、模型路由统计
 */

import { useEffect, useState } from 'react'

interface RouterStats {
  local_calls: number
  cloud_calls: number
  degrade_active: boolean
  budget_remaining: number
  budget_ratio: number
  daily_budget: number
  total_cost: number
}

interface DashboardProps {
  className?: string
}

function Dashboard({ className }: DashboardProps) {
  const [stats, setStats] = useState<RouterStats | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    fetchStats()
    const interval = setInterval(fetchStats, 10000) // 每10秒刷新
    return () => clearInterval(interval)
  }, [])

  const fetchStats = async () => {
    try {
      const resp = await fetch('/router/stats')
      if (resp.ok) {
        const data = await resp.json()
        setStats(data)
      }
    } catch (e) {
      console.error('获取路由统计失败:', e)
    }
    setLoading(false)
  }

  const totalCalls = (stats?.local_calls || 0) + (stats?.cloud_calls || 0)
  const localPercent = totalCalls > 0 ? ((stats?.local_calls || 0) / totalCalls * 100) : 0
  const cloudPercent = totalCalls > 0 ? ((stats?.cloud_calls || 0) / totalCalls * 100) : 0

  return (
    <div className={className} style={{
      background: '#1a1a2e',
      borderRadius: '12px',
      padding: '16px',
      display: 'flex',
      flexDirection: 'column',
      gap: '12px',
    }}>
      <h3 style={{ fontSize: '14px', color: '#00d4ff', margin: 0 }}>📊 成本监控</h3>

      {/* 预算使用进度条 */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px', fontSize: '12px', color: '#888' }}>
          <span>预算使用</span>
          <span style={{ color: (stats?.budget_ratio || 0) > 0.8 ? '#ef4444' : '#4ade80' }}>
            ${(stats?.total_cost || 0).toFixed(4)} / ${stats?.daily_budget?.toFixed(2) || '10.00'}
          </span>
        </div>
        <div style={{ height: '8px', background: '#2a2a4e', borderRadius: '4px', overflow: 'hidden' }}>
          <div style={{
            height: '100%',
            width: `${Math.min((stats?.budget_ratio || 0) * 100, 100)}%`,
            background: (stats?.budget_ratio || 0) > 0.8 ? '#ef4444' : (stats?.budget_ratio || 0) > 0.5 ? '#f59e0b' : '#4ade80',
            transition: 'width 0.3s',
          }} />
        </div>
      </div>

      {/* 模型路由饼图（简单横向条形） */}
      <div>
        <div style={{ fontSize: '12px', color: '#888', marginBottom: '6px' }}>模型调用分布</div>
        <div style={{ display: 'flex', height: '20px', borderRadius: '4px', overflow: 'hidden' }}>
          <div style={{
            width: `${localPercent}%`,
            background: '#3b82f6',
            transition: 'width 0.3s',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '10px',
            color: '#fff',
          }}>
            {localPercent > 10 ? `本地 ${localPercent.toFixed(0)}%` : ''}
          </div>
          <div style={{
            width: `${cloudPercent}%`,
            background: '#a78bfa',
            transition: 'width 0.3s',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '10px',
            color: '#fff',
          }}>
            {cloudPercent > 10 ? `云端 ${cloudPercent.toFixed(0)}%` : ''}
          </div>
        </div>
        <div style={{ display: 'flex', gap: '12px', marginTop: '6px', fontSize: '11px', color: '#888' }}>
          <span style={{ color: '#3b82f6' }}>● 本地: {stats?.local_calls || 0}</span>
          <span style={{ color: '#a78bfa' }}>● 云端: {stats?.cloud_calls || 0}</span>
        </div>
      </div>

      {/* 降级状态 */}
      {stats?.degrade_active && (
        <div style={{
          padding: '8px',
          background: '#f59e0b20',
          borderRadius: '6px',
          fontSize: '12px',
          color: '#f59e0b',
          textAlign: 'center',
        }}>
          ⚠️ 预算不足，已启用降级模式
        </div>
      )}

      {/* 总调用次数 */}
      <div style={{ fontSize: '12px', color: '#666', textAlign: 'center' }}>
        总调用: {totalCalls} 次
      </div>
    </div>
  )
}

export default Dashboard
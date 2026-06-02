/**
 * types.ts — V0.7 共享类型定义
 */

export type ConnectionState = 'connecting' | 'connected' | 'disconnected' | 'reconnecting'

export interface RouterStats {
  local_calls: number
  cloud_calls: number
  budget_remaining: number
  budget_ratio: number
  degrade_active: boolean
}
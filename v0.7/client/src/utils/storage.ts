/**
 * storage.ts — 统一的 localStorage / sessionStorage 访问层
 *
 * 目的：
 *   1. 集中版本号：所有键名带前缀 `v{VERSION}_`，旧数据自动失效
 *   2. 失败兜底：localStorage 可能满 / 禁用，统一 try/catch
 *   3. 类型安全：JSON.parse 失败时不返回垃圾
 *
 * 用法：
 *   import { storage } from '../utils/storage'
 *   storage.set('world', worldData)       // sessionStorage 默认
 *   storage.set('world', worldData, { persistent: true })
 *   const w = storage.get<WorldData>('world')
 */

const VERSION = 1
const PREFIX = `athenaeum_v${VERSION}_`

export interface SetOptions {
  persistent?: boolean // 走 localStorage（默认 sessionStorage）
}

function backend(opts?: SetOptions): Storage {
  return opts?.persistent ? window.localStorage : window.sessionStorage
}

export const storage = {
  /**
   * 写入；返回是否成功（false = 满 / 禁用 / 序列化失败）
   */
  set<T>(key: string, value: T, opts?: SetOptions): boolean {
    const fullKey = PREFIX + key
    try {
      backend(opts).setItem(fullKey, JSON.stringify(value))
      return true
    } catch (e) {
      console.warn(`[storage.set] ${fullKey} 写入失败:`, e)
      return false
    }
  },

  /**
   * 读取；返回 T 或 null（不存在 / 反序列化失败 / 旧版本）
   */
  get<T>(key: string, opts?: SetOptions): T | null {
    const fullKey = PREFIX + key
    try {
      const raw = backend(opts).getItem(fullKey)
      if (raw === null) return null
      return JSON.parse(raw) as T
    } catch (e) {
      console.warn(`[storage.get] ${fullKey} 解析失败:`, e)
      return null
    }
  },

  remove(key: string, opts?: SetOptions): void {
    try {
      backend(opts).removeItem(PREFIX + key)
    } catch (e) {
      console.warn(`[storage.remove] ${key} 失败:`, e)
    }
  },

  /**
   * 清理：删除所有以当前版本前缀的键。
   * 旧版本（无前缀或不同前缀）的键保留——调用方可在迁移完成后手动清理。
   */
  clearAll(opts?: SetOptions): number {
    const store = backend(opts)
    let removed = 0
    try {
      for (let i = store.length - 1; i >= 0; i--) {
        const k = store.key(i)
        if (k && k.startsWith(PREFIX)) {
          store.removeItem(k)
          removed++
        }
      }
    } catch (e) {
      console.warn('[storage.clearAll] 失败:', e)
    }
    return removed
  },

  /**
   * 列出所有当前版本前缀的键（不含前缀）
   */
  listKeys(opts?: SetOptions): string[] {
    const store = backend(opts)
    const keys: string[] = []
    try {
      for (let i = 0; i < store.length; i++) {
        const k = store.key(i)
        if (k && k.startsWith(PREFIX)) keys.push(k.slice(PREFIX.length))
      }
    } catch (e) {
      console.warn('[storage.listKeys] 失败:', e)
    }
    return keys
  },
}

export const STORAGE_VERSION = VERSION

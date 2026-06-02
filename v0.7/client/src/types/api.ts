/**
 * api.ts — 后端响应的 zod schemas
 *
 * 目的：把后端 API 的响应在客户端用 zod 校验，
 * 避免 `as any` 把 TS 类型系统关掉。
 *
 * 注意：这些 schema 是"客户端看到的形状"，不强制 1:1 匹配 Pydantic 输出。
 * 后端可加字段，zod 用 .passthrough() 或省略即可；后端缺字段会得到 parse 失败 → 安全失败。
 */
import { z } from 'zod'

// ---------- 基础标量 ----------

const finiteNumber = z.number().finite()

// ---------- 角色 / Agent ----------

const PersonalitySchema = z
  .object({
    openness: finiteNumber,
    conscientiousness: finiteNumber,
    extraversion: finiteNumber,
    agreeableness: finiteNumber,
    neuroticism: finiteNumber,
  })
  .partial()
  .passthrough()

const SoulDesireSchema = z.object({
  name: z.string(),
  level: finiteNumber,
})

const SoulInnerConflictSchema = z.object({
  description: z.string(),
}).passthrough()

const SubconsciousRuleSchema = z.object({
  trigger: z.string(),
  action: z.string(),
})

const SoulSchema = z
  .object({
    core_desires: z.array(SoulDesireSchema).optional(),
    inner_conflict: SoulInnerConflictSchema.optional(),
    subconscious_rules: z.array(SubconsciousRuleSchema).optional(),
  })
  .partial()
  .passthrough()

const EmotionStateSchema = z.object({
  label: z.string(),
  valence: finiteNumber,
  arousal: finiteNumber,
})

export const ActiveGoalSchema = z
  .object({
    id: z.union([z.string(), z.null()]).optional(),
    type: z.string().optional(),
    description: z.string().optional(),
    progress: finiteNumber.optional(),
  })
  .passthrough()

const AgentSchema = z
  .object({
    id: z.string(),
    name: z.string(),
    location: z.string(),
    occupation: z.string().optional(),
    personality: PersonalitySchema.optional(),
    soul: SoulSchema.optional(),
    emotion_state: EmotionStateSchema.optional(),
    active_goal: z.union([z.string(), ActiveGoalSchema]).nullable().optional(),
    goal_progress: finiteNumber.optional(),
    neighbors: z.array(z.string()).optional(),
    is_active: z.boolean().default(false),
    mood: z.string().nullable().optional(),
    intention: z.string().optional(),
    extended_personality: z.record(z.string(), finiteNumber).optional(),
    current_action: z.string().nullable().optional(),
    last_decision: z.record(z.string(), z.any()).nullable().optional(),
  })
  .passthrough()

export type Agent = z.infer<typeof AgentSchema>

// ---------- 地点 / Location ----------

export const LocationSchema = z
  .object({
    id: z.string(),
    name: z.string(),
    tags: z.array(z.string()).optional().default([]),
    agents: z.array(z.string()).optional().default([]),
  })
  .passthrough()

export type Location = z.infer<typeof LocationSchema>

// ---------- 对话 ----------

export const DialogueEntrySchema = z
  .object({
    from: z.string(),
    from_id: z.string(),
    to: z.string(),
    utterance: z.string(),
    micro_action: z.string().optional(),
    tick: z.number().int().nonnegative(),
  })
  .passthrough()

export type DialogueEntry = z.infer<typeof DialogueEntrySchema>

// ---------- 行动 ----------

export const ActionEntrySchema = z
  .object({
    agent_id: z.string(),
    agent_name: z.string(),
    action_type: z.string(),
    description: z.string(),
    target_location: z.string().nullable(),
    tick: z.number().int().nonnegative(),
  })
  .passthrough()

export type ActionEntry = z.infer<typeof ActionEntrySchema>

// ---------- 世界状态 ----------

export const WorldStateSchema = z
  .object({
    tick_id: z.number().int().nonnegative(),
    time: z
      .object({
        game_hour: finiteNumber,
        time_of_day: z.string(),
      })
      .optional(),
    weather: z.string().optional().default('unknown'),
    tick_type: z.string().optional().default('normal'),
    agents: z.array(AgentSchema).default([]),
    locations: z.array(LocationSchema).default([]),
    recent_dialogues: z.array(DialogueEntrySchema).default([]),
    recent_actions: z.array(ActionEntrySchema).default([]),
  })
  .passthrough()

export type WorldState = z.infer<typeof WorldStateSchema>

// ---------- 路由统计 ----------

export const RouterStatsSchema = z
  .object({
    local_calls: z.number().int().nonnegative(),
    cloud_calls: z.number().int().nonnegative(),
    degrade_active: z.boolean(),
    budget_remaining: finiteNumber,
    budget_ratio: finiteNumber,
    daily_budget: finiteNumber,
    total_cost: finiteNumber,
  })
  .passthrough()

export type RouterStats = z.infer<typeof RouterStatsSchema>

// ---------- 健康检查 ----------

export const HealthResponseSchema = z
  .object({
    status: z.enum(['healthy', 'degraded']),
    version: z.string(),
    local_llm: z.string(),
    cloud_llm: z.string(),
  })
  .passthrough()

export type HealthResponse = z.infer<typeof HealthResponseSchema>

// ---------- 解析工具：安全 fetch + 校验 ----------

/**
 * fetchJson — fetch URL 并用 zod schema 校验响应。
 * 失败时不抛，返回 null（前端可降级渲染）。
 * 返回类型从 schema 自动推导：`fetchJson(url, HealthResponseSchema)` → `Promise<HealthResponse | null>`.
 */
export async function fetchJson<S extends z.ZodTypeAny>(
  url: string,
  schema: S,
  init?: RequestInit,
): Promise<z.infer<S> | null> {
  try {
    const res = await fetch(url, init)
    if (!res.ok) {
      console.warn(`[fetchJson] ${url} -> HTTP ${res.status}`)
      return null
    }
    const raw = await res.json()
    const parsed = schema.safeParse(raw)
    if (!parsed.success) {
      console.warn(
        `[fetchJson] ${url} schema mismatch:`,
        parsed.error.issues.slice(0, 3),
      )
      return null
    }
    return parsed.data
  } catch (e) {
    console.warn(`[fetchJson] ${url} network error:`, e)
    return null
  }
}

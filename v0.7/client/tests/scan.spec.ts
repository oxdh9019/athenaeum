/**
 * scan.spec.ts — 全页面健康扫描
 *
 * 目的：逐个 tab 访问，采集 console errors / network failures / 渲染问题，
 * 生成结构化报告，不依赖真实 LLM（用 /world/apply 直接灌数据）。
 *
 * 运行：npx playwright test tests/scan.spec.ts
 * 前置：FastAPI 服务在 :8000，前端已 build。
 */

import { test, expect, type Page, type ConsoleMessage } from '@playwright/test'
import { writeFileSync, mkdirSync, existsSync } from 'fs'

const BASE_URL = 'http://localhost:8000'
const SCREENSHOT_DIR = '/tmp/athenaeum_scan'
if (!existsSync(SCREENSHOT_DIR)) mkdirSync(SCREENSHOT_DIR, { recursive: true })

interface Issue {
  tab: string
  severity: 'error' | 'warning' | 'observation'
  message: string
  stack?: string
}

const issues: Issue[] = []
const consoleMsgs: { tab: string; type: string; text: string }[] = []
const networkFails: { tab: string; url: string; status: number }[] = []

const TEST_WORLD = {
  world: {
    name: '扫描测试小镇',
    description: '一个简短的扫描测试世界',
    locations: [
      { id: 'lib', name: '图书馆', tags: ['quiet'], capacity: 5 },
      { id: 'cafe', name: '咖啡厅', tags: ['social'], capacity: 5 },
      { id: 'park', name: '公园', tags: ['outdoor'], capacity: 5 },
    ],
    time_rules: { day_start_hour: 6, day_end_hour: 22, tick_interval_minutes: 30 },
    atmosphere: { mood: 'peaceful', dominant_themes: ['daily life'], ambient_sounds: ['birds'] },
  },
  characters: [
    {
      id: 'scan_a', name: '扫描A', age: 28, occupation: '图书管理员',
      personality: { openness: 0.7, conscientiousness: 0.6, extraversion: 0.4, agreeableness: 0.7, neuroticism: 0.3 },
      identity_tags: { primary: '学者', secondary: ['细心'], self_identity: '守护知识' },
      backstory: '在图书馆工作多年',
      initial_location: 'lib',
      soul: {
        core_desires: ['传播知识', '保持独处'],
        inner_conflict: { pole_a: '渴望交流', pole_b: '害怕被打扰', description: '在借出与安静之间犹豫' },
        subconscious_rules: [{ trigger: '看到有人翻书', action: '目光停留', priority: 0.3 }],
        behavioral_tendencies: { introvert: 0.7 },
        long_term_goals: ['整理藏书'],
      },
    },
    {
      id: 'scan_b', name: '扫描B', age: 35, occupation: '咖啡师',
      personality: { openness: 0.5, conscientiousness: 0.6, extraversion: 0.8, agreeableness: 0.6, neuroticism: 0.4 },
      identity_tags: { primary: '匠人', secondary: ['健谈'], self_identity: '用咖啡连接人' },
      backstory: '经营咖啡厅十年',
      initial_location: 'cafe',
      soul: {
        core_desires: ['与人交流', '被需要'],
        inner_conflict: { pole_a: '渴望更深友谊', pole_b: '满足于表面熟络', description: '少有真正的知己' },
        subconscious_rules: [{ trigger: '看到有人进门', action: '主动打招呼', priority: 0.5 }],
        behavioral_tendencies: { extrovert: 0.8 },
        long_term_goals: ['开分店'],
      },
    },
  ],
  relationships: [
    { from_id: 'scan_a', to_id: 'scan_b', relationship_type: '熟悉', strength: 0.6, shared_history: '常去咖啡厅', potential_conflicts: [] },
  ],
}

async function instrumentPage(page: Page, tabName: string) {
  page.on('console', (msg: ConsoleMessage) => {
    const type = msg.type()
    if (type === 'error' || type === 'warning') {
      consoleMsgs.push({ tab: tabName, type, text: msg.text() })
    }
  })
  page.on('pageerror', (err) => {
    issues.push({ tab: tabName, severity: 'error', message: `Uncaught: ${err.message}`, stack: err.stack })
  })
  page.on('response', (resp) => {
    const url = resp.url()
    if (!url.startsWith(BASE_URL)) return
    const status = resp.status()
    if (status >= 400) {
      networkFails.push({ tab: tabName, url, status })
    }
  })
}

async function clickTab(page: Page, tabName: string) {
  await page.locator(`.app-nav button:has-text("${tabName}")`).click()
  await page.waitForTimeout(800)
}

test.describe.serial('V0.7 全页面健康扫描', () => {

  test('S0. 准备：应用测试世界 + 启动', async ({ request }) => {
    test.setTimeout(60000)
    const resp = await request.post(`${BASE_URL}/world/apply`, { data: TEST_WORLD })
    expect(resp.ok()).toBeTruthy()
    const json = await resp.json()
    expect(json.agent_count).toBe(2)
    console.log(`✓ 测试世界已应用: ${json.message}`)

    await request.post(`${BASE_URL}/world/start`)
    await new Promise(r => setTimeout(r, 8000))
    const r = await request.get(`${BASE_URL}/world/state`)
    const d = await r.json()
    console.log(`✓ 世界已启动, tick=${d.tick_id}, agents=${d.agents.length}`)
  })

  test('S1. Tab: 仪表盘', async ({ page }) => {
    await page.goto(BASE_URL)
    await page.waitForLoadState('networkidle')
    await instrumentPage(page, '仪表盘')
    await clickTab(page, '仪表盘')
    await page.waitForTimeout(2000)

    await page.screenshot({ path: `${SCREENSHOT_DIR}/01_dashboard.png`, fullPage: true })

    const dashboardVisible = await page.locator('.dashboard').isVisible().catch(() => false)
    expect(dashboardVisible, 'Dashboard 容器可见').toBeTruthy()

    // 检查关键内容
    const agentCount = await page.locator('.dashboard .agent-card, .dashboard .stat-value').count()
    if (agentCount === 0) {
      issues.push({ tab: '仪表盘', severity: 'observation', message: '无 agent-card 渲染,可能因为 agents=[]' })
    }

    const stats = await page.locator('.dashboard .stat-grid .stat-value').allTextContents()
    console.log(`仪表盘统计: ${JSON.stringify(stats)}`)
  })

  test('S2. Tab: 角色', async ({ page }) => {
    await page.goto(BASE_URL)
    await page.waitForLoadState('networkidle')
    await instrumentPage(page, '角色')
    await clickTab(page, '角色')
    await page.waitForTimeout(2000)
    await page.screenshot({ path: `${SCREENSHOT_DIR}/02_agents.png`, fullPage: true })

    const cardCount = await page.locator('.agent-card').count()
    console.log(`角色卡片数: ${cardCount}`)
    if (cardCount === 0) {
      issues.push({ tab: '角色', severity: 'error', message: 'agents>0 但无 agent-card 渲染' })
    }

    // 试点击第一个角色
    if (cardCount > 0) {
      await page.locator('.agent-card').first().click()
      await page.waitForTimeout(800)
      const detailVisible = await page.locator('.agent-detail, .agent-card-detail').first().isVisible().catch(() => false)
      console.log(`点第一个角色后详情可见: ${detailVisible}`)
    }
  })

  test('S3. Tab: 对话', async ({ page }) => {
    await page.goto(BASE_URL)
    await page.waitForLoadState('networkidle')
    await instrumentPage(page, '对话')
    await clickTab(page, '对话')
    await page.waitForTimeout(2000)
    await page.screenshot({ path: `${SCREENSHOT_DIR}/03_dialogue.png`, fullPage: true })

    const viewVisible = await page.locator('.dialogue-view').isVisible().catch(() => false)
    expect(viewVisible).toBeTruthy()

    const selects = await page.locator('.dialogue-view select').count()
    const startBtn = await page.locator('.dialogue-view button:has-text("开始对话")').isVisible().catch(() => false)
    console.log(`对话: ${selects} 个选择器, 开始按钮=${startBtn}`)

    // 试着启动一次对话
    if (selects >= 2 && startBtn) {
      const optLabels = await page.locator('.dialogue-view select option').allTextContents()
      console.log(`agent 选项: ${JSON.stringify(optLabels.slice(0, 5))}`)
      if (optLabels.length >= 3) {
        await page.locator('.dialogue-view select').first().selectOption({ index: 1 })
        await page.locator('.dialogue-view select').last().selectOption({ index: 2 })
        await page.locator('.dialogue-view button:has-text("开始对话")').click()
        await page.waitForTimeout(3000)
        const logVisible = await page.locator('.dialogue-log, .dialogue-messages').first().isVisible().catch(() => false)
        console.log(`对话启动后日志可见: ${logVisible}`)
        if (!logVisible) {
          issues.push({ tab: '对话', severity: 'warning', message: '点击开始对话后无 dialogue-log 渲染' })
        }
      }
    }
  })

  test('S4. Tab: 灵魂', async ({ page }) => {
    await page.goto(BASE_URL)
    await page.waitForLoadState('networkidle')
    await instrumentPage(page, '灵魂')
    await clickTab(page, '灵魂')
    await page.waitForTimeout(2000)
    await page.screenshot({ path: `${SCREENSHOT_DIR}/04_soul.png`, fullPage: true })

    const viewVisible = await page.locator('.soul-view').isVisible().catch(() => false)
    expect(viewVisible).toBeTruthy()

    // 没有 selectedAgent 时显示空状态
    const emptyText = await page.locator('.soul-view .empty, .soul-view p').first().textContent().catch(() => '')
    console.log(`灵魂视图内容(无 selected): ${emptyText?.slice(0, 80)}`)
  })

  test('S5. Tab: 工坊', async ({ page }) => {
    await page.goto(BASE_URL)
    await page.waitForLoadState('networkidle')
    await instrumentPage(page, '工坊')
    await clickTab(page, '工坊')
    await page.waitForTimeout(2000)
    await page.screenshot({ path: `${SCREENSHOT_DIR}/05_worldsmith.png`, fullPage: true })

    const viewVisible = await page.locator('.worldsmith-view').isVisible().catch(() => false)
    expect(viewVisible).toBeTruthy()

    const generateBtn = await page.locator('.worldsmith-view button:has-text("开始生成")').isVisible().catch(() => false)
    const applyBtn = await page.locator('.worldsmith-view button:has-text("应用到引擎")').isVisible().catch(() => false)
    console.log(`工坊: 生成按钮=${generateBtn}, 应用按钮=${applyBtn}`)

    // 试填一个描述,看是否生成按钮可点
    const ta = page.locator('.worldsmith-view textarea').first()
    if (await ta.isVisible().catch(false)) {
      await ta.fill('扫描测试用世界。')
      await page.waitForTimeout(300)
      const enabled = await page.locator('.worldsmith-view button:has-text("开始生成")').isEnabled().catch(() => false)
      console.log(`填描述后生成按钮可点击: ${enabled}`)
    }
  })

  test('S6. Tab: 日记', async ({ page }) => {
    await page.goto(BASE_URL)
    await page.waitForLoadState('networkidle')
    await instrumentPage(page, '日记')
    await clickTab(page, '日记')
    await page.waitForTimeout(2000)
    await page.screenshot({ path: `${SCREENSHOT_DIR}/06_diary.png`, fullPage: true })

    const viewVisible = await page.locator('.diary-view, [class*="diary"]').first().isVisible().catch(() => false)
    console.log(`日记视图可见: ${viewVisible}`)

    // 看是否需要先选 agent
    const memCount = await page.locator('.memory-item, .diary-entry').count()
    console.log(`日记条数: ${memCount}`)
    if (memCount === 0) {
      issues.push({ tab: '日记', severity: 'observation', message: '日记无内容(预期:无 dialogue → 无归档 → 无记忆)' })
    }
  })

  test('S7. Tab: 时间线', async ({ page }) => {
    await page.goto(BASE_URL)
    await page.waitForLoadState('networkidle')
    await instrumentPage(page, '时间线')
    await clickTab(page, '时间线')
    await page.waitForTimeout(2000)
    await page.screenshot({ path: `${SCREENSHOT_DIR}/07_timeline.png`, fullPage: true })

    const viewVisible = await page.locator('.timeline-view, [class*="timeline"]').first().isVisible().catch(() => false)
    const eventCount = await page.locator('.timeline-event, .timeline-item').count()
    console.log(`时间线视图: ${viewVisible}, 事件数: ${eventCount}`)
    if (eventCount === 0) {
      issues.push({ tab: '时间线', severity: 'observation', message: '时间线无事件(预期:端点 /world/timeline 未实现)' })
    }
  })

  test('S8. Tab: 地图', async ({ page }) => {
    await page.goto(BASE_URL)
    await page.waitForLoadState('networkidle')
    await instrumentPage(page, '地图')
    await clickTab(page, '地图')
    await page.waitForTimeout(2000)
    await page.screenshot({ path: `${SCREENSHOT_DIR}/08_map.png`, fullPage: true })

    const viewVisible = await page.locator('.map-view, canvas, svg').first().isVisible().catch(() => false)
    console.log(`地图视图可见: ${viewVisible}`)

    // 看 agent 节点是否存在
    const agentNodeCount = await page.locator('.map-agent, .agent-node').count()
    console.log(`地图上 agent 节点数: ${agentNodeCount}`)
  })

  test('S9. Tab: 附身', async ({ page }) => {
    await page.goto(BASE_URL)
    await page.waitForLoadState('networkidle')
    await instrumentPage(page, '附身')
    await clickTab(page, '附身')
    await page.waitForTimeout(2000)
    await page.screenshot({ path: `${SCREENSHOT_DIR}/09_possess.png`, fullPage: true })

    const promptText = await page.locator('text=请先在左侧选择一个角色进行附身').isVisible().catch(() => false)
    console.log(`附身空状态提示: ${promptText}`)
  })

  test('S10. 控制栏：暂停 / 恢复', async ({ page }) => {
    await page.goto(BASE_URL)
    await page.waitForLoadState('networkidle')
    await instrumentPage(page, '控制栏')
    await page.waitForTimeout(2000)

    const pauseBtn = page.locator('.control-bar button:has-text("暂停")')
    if (await pauseBtn.isVisible()) {
      await pauseBtn.click()
      await page.waitForTimeout(1500)
      const t1 = await page.evaluate(async () => {
        const r = await fetch('/world/state')
        const d = await r.json()
        return d.tick_id
      })
      await page.waitForTimeout(2000)
      const t2 = await page.evaluate(async () => {
        const r = await fetch('/world/state')
        const d = await r.json()
        return d.tick_id
      })
      console.log(`暂停时 tick: t1=${t1} t2=${t2} (应相等)`)
      if (t1 !== t2) {
        issues.push({ tab: '控制栏', severity: 'error', message: `暂停时 tick 仍推进 (${t1}→${t2})` })
      }
      const resumeBtn = page.locator('.control-bar button:has-text("恢复"), .control-bar button:has-text("继续")')
      if (await resumeBtn.isVisible()) {
        await resumeBtn.click()
        await page.waitForTimeout(2000)
        const t3 = await page.evaluate(async () => {
          const r = await fetch('/world/state')
          const d = await r.json()
          return d.tick_id
        })
        console.log(`恢复后 tick: ${t3} (应 > t2=${t2})`)
        if (t3 <= t2) {
          issues.push({ tab: '控制栏', severity: 'error', message: `恢复后 tick 未推进 (t2=${t2}, t3=${t3})` })
        }
      }
    }
  })

  test.afterAll(async () => {
    const report = {
      generatedAt: new Date().toISOString(),
      issues,
      consoleMsgs: consoleMsgs.slice(0, 50),
      networkFails,
      summary: {
        totalIssues: issues.length,
        errors: issues.filter(i => i.severity === 'error').length,
        warnings: issues.filter(i => i.severity === 'warning').length,
        observations: issues.filter(i => i.severity === 'observation').length,
        consoleErrors: consoleMsgs.filter(m => m.type === 'error').length,
        networkFailures: networkFails.length,
      },
    }
    writeFileSync('/tmp/athenaeum_scan_report.json', JSON.stringify(report, null, 2))
    writeFileSync('/tmp/athenaeum_scan_report.md', renderMarkdown(report))
    console.log('\n===== 扫描报告 =====')
    console.log(`问题数: ${report.summary.totalIssues} (errors=${report.summary.errors}, warnings=${report.summary.warnings}, observations=${report.summary.observations})`)
    console.log(`console errors: ${report.summary.consoleErrors}`)
    console.log(`网络失败: ${report.summary.networkFailures}`)
    console.log(`报告: /tmp/athenaeum_scan_report.{json,md}`)
    console.log(`截图: ${SCREENSHOT_DIR}/`)
  })
})

function renderMarkdown(r: any): string {
  const lines: string[] = []
  lines.push(`# Athenaeum 全页面健康扫描报告`)
  lines.push(`生成时间: ${r.generatedAt}`)
  lines.push(``)
  lines.push(`## 汇总`)
  lines.push(`- 总问题: ${r.summary.totalIssues}`)
  lines.push(`- errors: ${r.summary.errors}`)
  lines.push(`- warnings: ${r.summary.warnings}`)
  lines.push(`- observations: ${r.summary.observations}`)
  lines.push(`- console errors: ${r.summary.consoleErrors}`)
  lines.push(`- 网络失败: ${r.summary.networkFailures}`)
  lines.push(``)
  if (r.issues.length) {
    lines.push(`## 问题列表`)
    for (const i of r.issues) {
      lines.push(`- **[${i.severity}]** \`${i.tab}\`: ${i.message}`)
    }
    lines.push(``)
  }
  if (r.consoleMsgs.length) {
    lines.push(`## Console 错误/警告(最多 50 条)`)
    for (const m of r.consoleMsgs) {
      lines.push(`- [${m.type}] \`${m.tab}\`: ${m.text.slice(0, 200)}`)
    }
    lines.push(``)
  }
  if (r.networkFails.length) {
    lines.push(`## 网络失败`)
    for (const n of r.networkFails) {
      lines.push(`- [${n.tab}] ${n.status} ${n.url}`)
    }
    lines.push(``)
  }
  return lines.join('\n')
}

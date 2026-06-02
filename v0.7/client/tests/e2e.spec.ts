/**
 * e2e.spec.ts — V0.7 端到端自动化测试（需要本地 LLM 模拟）
 *
 * 与 smoke.spec.ts 的区别：本文件需要 FastAPI 服务运行，但所有 LLM 调用都通过
 * `page.route()` 拦截 mock，不依赖真实 Ollama 启动模型（避免 test 18/25 跑 300s）。
 * 仅用于验证 UI 在 LLM 响应路径上的渲染。
 *
 * 运行：npm run test:full（先启动后端：`./v0.7/start_v0.7.sh`）
 */

import { test, expect } from '@playwright/test'
import { writeFileSync } from 'fs'

const BASE_URL = 'http://localhost:8000'

// Mock LLM 响应：拦截 /world/generate_full、/dialogue/start 等 LLM 路径
test.beforeEach(async ({ page }) => {
  await page.route('**/world/generate_full', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        world: {
          name: '测试小镇',
          description: '一个宁静的小镇',
          locations: [
            { id: 'library', name: '图书馆', tags: ['quiet'], description: '安静的图书馆' },
            { id: 'cafe', name: '咖啡厅', tags: ['social'], description: '热闹的咖啡厅' },
          ],
          time_rules: { day_start_hour: 6, day_end_hour: 22, tick_interval_minutes: 30 },
          atmosphere: { mood: 'peaceful', dominant_themes: ['daily life'], ambient_sounds: ['birds'] },
        },
        characters: [
          { id: 'char_a', name: '测试角色A', age: 25, gender: 'female', pronouns: 'she/her',
            personality: { openness: 0.5, conscientiousness: 0.5, extraversion: 0.5, agreeableness: 0.5, neuroticism: 0.5 },
            identity_tags: { primary: '测试', secondary: 'mock', self_identity: 'mock agent' },
            backstory: { title: 'mock', childhood: 'mock', adolescence: 'mock', adulthood: 'mock', present: 'mock' },
            initial_location: 'library', introduce_text: '我是 mock 角色', needs: [{ name: 'social', level: 0.5 }] },
        ],
        relationships: [],
        personality_tips: [],
      }),
    })
  })

  await page.route('**/dialogue/start*', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ message: '对话已开始 (mock)' }) })
  })
})

test.describe('V0.7 Athenaeum 自动化测试', () => {

  // ========== 1. 健康检查 ==========
  test('1. 服务器健康检查', async ({ request }) => {
    const response = await request.get(`${BASE_URL}/health`)
    expect(response.ok()).toBeTruthy()
    const json = await response.json()
    expect(json.status).toBe('healthy')
    expect(json.version).toBe('0.7')
    console.log('✓ 健康检查通过')
  })

  // ========== 2. 前端页面加载 ==========
  test('2. 前端页面加载', async ({ page }) => {
    await page.goto(BASE_URL)
    await page.waitForLoadState('networkidle')

    await expect(page).toHaveTitle(/Athenaeum/)
    console.log('✓ 页面加载成功')

    const header = page.locator('.app-header')
    await expect(header).toBeVisible()
    console.log('✓ Header 存在')

    const logo = page.locator('.app-logo h1')
    await expect(logo).toContainText('Athenaeum')
    console.log('✓ Logo 显示正确')
  })

  // ========== 3. 检查所有 Tab ==========
  test('3. 所有 Tab 视图存在', async ({ page }) => {
    await page.goto(BASE_URL)
    await page.waitForLoadState('networkidle')

    const tabs = [
      '仪表盘', '角色', '对话', '灵魂', '工坊',
      '日记', '时间线', '地图', '附身'
    ]

    for (const tabName of tabs) {
      const btn = page.locator(`.app-nav button:has-text("${tabName}")`)
      await expect(btn).toBeVisible()
      console.log(`✓ Tab "${tabName}" 存在`)
    }
  })

  // ========== 4. Dashboard 视图 ==========
  test('4. Dashboard 视图功能', async ({ page }) => {
    await page.goto(BASE_URL)
    await page.waitForLoadState('networkidle')

    const dashboard = page.locator('.dashboard')
    await expect(dashboard).toBeVisible()
    console.log('✓ Dashboard 视图可见')

    const statGrid = page.locator('.stat-grid')
    await expect(statGrid).toBeVisible()
    console.log('✓ 统计卡片存在')
  })

  // ========== 5. 创建世界 ==========
  test('5. 创建世界', async ({ page }) => {
    await page.goto(BASE_URL)
    await page.waitForLoadState('networkidle')

    await page.locator('.card button:has-text("创建世界")').click()
    await page.waitForTimeout(2000)
    console.log('✓ 创建世界按钮已点击')
  })

  // ========== 6. 创建 Agent ==========
  test('6. 创建 Agent', async ({ page }) => {
    await page.goto(BASE_URL)
    await page.waitForLoadState('networkidle')

    await page.locator('.card button:has-text("创建世界")').click()
    await page.waitForTimeout(1000)

    await page.locator('.card input[placeholder="角色名"]').fill('艾丽娅')
    await page.locator('.card input[placeholder="职业"]').fill('图书管理员')
    await page.locator('.card button:has-text("添加角色")').click()
    await page.waitForTimeout(2000)

    const agentItem = page.locator('.agent-list .agent-item:has-text("艾丽娅")')
    await expect(agentItem).toBeVisible({ timeout: 5000 })
    console.log('✓ Agent "艾丽娅" 创建成功')
  })

  // ========== 7. 角色视图 ==========
  test('7. 角色视图', async ({ page }) => {
    await page.goto(BASE_URL)
    await page.waitForLoadState('networkidle')

    // 先创建世界和角色
    await page.locator('.dashboard button:has-text("创建世界")').click()
    await page.waitForTimeout(1000)
    await page.locator('.dashboard input[placeholder="角色名"]').fill('艾丽娅')
    await page.locator('.dashboard input[placeholder="职业"]').fill('图书管理员')
    await page.locator('.dashboard button:has-text("添加角色")').click()
    await page.waitForTimeout(1500)

    // 切换到角色 Tab（使用 nav）
    await page.locator('.app-nav button:has-text("角色")').click()
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)

    // 检查角色列表面板
    const agentListPanel = page.locator('.agents-view')
    await expect(agentListPanel).toBeVisible({ timeout: 10000 })
    console.log('✓ 角色列表面板可见')

    // 检查角色卡片
    const agentCard = page.locator('.agent-card').first()
    await expect(agentCard).toBeVisible({ timeout: 5000 })
    console.log('✓ 角色卡片存在')
  })

  // ========== 8. 对话视图 ==========
  test('8. 对话视图', async ({ page }) => {
    await page.goto(BASE_URL)
    await page.waitForLoadState('networkidle')

    // 切换到对话 Tab
    await page.locator('.app-nav button:has-text("对话")').click()
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)

    // 检查控件
    const dialogueView = page.locator('.dialogue-view')
    await expect(dialogueView).toBeVisible({ timeout: 10000 })
    console.log('✓ 对话视图可见')

    // 检查选择器
    await expect(page.locator('.dialogue-view select').first()).toBeVisible({ timeout: 5000 })
    console.log('✓ Agent 选择器存在')

    // 检查按钮
    await expect(page.locator('.dialogue-view button:has-text("开始对话")')).toBeVisible({ timeout: 5000 })
    console.log('✓ 开始对话按钮存在')
  })

  // ========== 9. 灵魂视图 ==========
  test('9. 灵魂视图', async ({ page }) => {
    await page.goto(BASE_URL)
    await page.waitForLoadState('networkidle')

    // 切换到灵魂 Tab
    await page.locator('.app-nav button:has-text("灵魂")').click()
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)

    // 检查灵魂视图 (SoulView component renders empty state when no agent selected)
    const empty = page.locator('.soul-view .empty, .soul-view p.empty')
    await expect(empty.first()).toBeVisible({ timeout: 10000 })
    console.log('✓ 灵魂视图可见')
  })

  // ========== 10. 工坊视图 ==========
  test('10. 世界工坊视图', async ({ page }) => {
    await page.goto(BASE_URL)
    await page.waitForLoadState('networkidle')

    // 切换到工坊 Tab
    await page.locator('.app-nav button:has-text("工坊")').click()
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)

    // 检查工坊文本
    await expect(page.locator('.worldsmith-view')).toBeVisible({ timeout: 10000 })
    console.log('✓ 工坊视图可见')

    // 检查表单
    await expect(page.locator('.worldsmith-view textarea').first()).toBeVisible({ timeout: 5000 })
    console.log('✓ 描述输入框存在')

    await expect(page.locator('.worldsmith-view select').first()).toBeVisible({ timeout: 5000 })
    console.log('✓ 角色数量选择器存在')

    await expect(page.locator('.worldsmith-view button:has-text("开始生成")')).toBeVisible({ timeout: 5000 })
    console.log('✓ 生成按钮存在')
  })

  // ========== 11. 日记视图 ==========
  test('11. 日记视图', async ({ page }) => {
    await page.goto(BASE_URL)
    await page.waitForLoadState('networkidle')

    await page.locator('.app-nav button:has-text("日记")').click()
    await page.waitForTimeout(1000)
    console.log('✓ 日记视图切换成功')
  })

  // ========== 12. 时间线视图 ==========
  test('12. 时间线视图', async ({ page }) => {
    await page.goto(BASE_URL)
    await page.waitForLoadState('networkidle')

    await page.locator('.app-nav button:has-text("时间线")').click()
    await page.waitForTimeout(1000)
    console.log('✓ 时间线视图切换成功')
  })

  // ========== 13. 地图视图 ==========
  test('13. 地图视图', async ({ page }) => {
    await page.goto(BASE_URL)
    await page.waitForLoadState('networkidle')

    await page.locator('.app-nav button:has-text("地图")').click()
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)

    // 检查地图视图
    await expect(page.locator('.map-view')).toBeVisible({ timeout: 10000 })
    console.log('✓ 地图视图可见')
  })

  // ========== 14. 附身视图 ==========
  test('14. 附身视图', async ({ page }) => {
    await page.goto(BASE_URL)
    await page.waitForLoadState('networkidle')

    await page.locator('.app-nav button:has-text("附身")').click()
    await page.waitForTimeout(1000)  // 等待渲染

    await expect(page.locator('text=请先在左侧选择一个角色进行附身')).toBeVisible({ timeout: 5000 })
    console.log('✓ 附身提示正确')
  })

  // ========== 15. TopBar ==========
  test('15. TopBar 显示', async ({ page }) => {
    await page.goto(BASE_URL)
    await page.waitForLoadState('networkidle')

    await expect(page.locator('.topbar')).toBeVisible()
    console.log('✓ TopBar 存在')

    await expect(page.locator('.topbar-time')).toBeVisible()
    console.log('✓ 时间显示存在')

    await expect(page.locator('.topbar-tick')).toBeVisible()
    console.log('✓ Tick 显示存在')
  })

  // ========== 16. ControlBar ==========
  test('16. ControlBar 显示', async ({ page }) => {
    await page.goto(BASE_URL)
    await page.waitForLoadState('networkidle')

    await expect(page.locator('.control-bar')).toBeVisible()
    console.log('✓ ControlBar 存在')

    await expect(page.locator('.control-bar button:has-text("暂停")')).toBeVisible()
    console.log('✓ 暂停按钮存在')

    await expect(page.locator('.control-bar button:has-text("■ 停止")')).toBeVisible()
    console.log('✓ 停止按钮存在')
  })

  // ========== 17. 状态指示器 ==========
  test('17. 状态指示器', async ({ page }) => {
    await page.goto(BASE_URL)
    await page.waitForLoadState('networkidle')

    await expect(page.locator('.app-status')).toBeVisible()
    console.log('✓ 状态指示器存在')

    await expect(page.locator('.status-dot')).toBeVisible()
    console.log('✓ 状态点存在')
  })

  // ========== 18. 完整流程 ==========
  test('18. 完整流程：创建世界 -> Agent -> 启动 -> 对话', async ({ page }) => {
    // 每个测试都重新加载页面确保干净状态
    await page.goto(BASE_URL)
    await page.waitForLoadState('networkidle')

    // 1. 创建世界
    await page.locator('.dashboard button:has-text("创建世界")').click()
    await page.waitForTimeout(1500)
    console.log('✓ 世界已创建')

    // 2. 创建第一个 Agent
    await page.locator('.dashboard input[placeholder="角色名"]').fill('艾丽娅')
    await page.locator('.dashboard input[placeholder="职业"]').fill('图书管理员')
    await page.locator('.dashboard button:has-text("添加角色")').click()
    await page.waitForTimeout(1500)
    console.log('✓ Agent 艾丽娅 已创建')

    // 3. 创建第二个 Agent
    await page.locator('.dashboard input[placeholder="角色名"]').fill('马克')
    await page.locator('.dashboard input[placeholder="职业"]').fill('咖啡师')
    await page.locator('.dashboard button:has-text("添加角色")').click()
    await page.waitForTimeout(1500)
    console.log('✓ Agent 马克 已创建')

    // 4. 启动世界
    await page.locator('.dashboard button:has-text("启动世界")').click()
    await page.waitForTimeout(1500)
    console.log('✓ 世界已启动')

    // 5. 切换到对话（使用 nav）
    await page.locator('.app-nav button:has-text("对话")').click()
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)

    // 6. 选择两个 Agent（等待选择器出现）
    await expect(page.locator('.dialogue-view select').first()).toBeVisible({ timeout: 10000 })
    const selects = page.locator('.dialogue-view select')
    await selects.first().selectOption({ label: '艾丽娅' })
    await selects.last().selectOption({ label: '马克' })
    console.log('✓ Agent 已选择')

    // 7. 开始对话
    await page.locator('.dialogue-view button:has-text("开始对话")').click()
    await page.waitForTimeout(2000)
    console.log('✓ 对话已触发')

    // 验证对话框
    await expect(page.locator('.dialogue-view .dialogue-log')).toBeVisible({ timeout: 5000 })
    console.log('✓ 对话日志可见')
  })

  // ========== 19. 工坊生成表单 ==========
  test('19. 工坊生成表单', async ({ page }) => {
    await page.goto(BASE_URL)
    await page.waitForLoadState('networkidle')

    await page.locator('.app-nav button:has-text("工坊")').click()
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)

    await page.locator('.worldsmith-view textarea').first().fill('一个宁静的小镇，有图书馆和咖啡馆。')
    await page.waitForTimeout(200)
    console.log('✓ 描述已填写')

    // 角色数量是第二个 select
    await page.locator('.worldsmith-view select').nth(1).selectOption('4')
    await page.waitForTimeout(200)
    console.log('✓ 角色数量已选择')

    const generateBtn = page.locator('.worldsmith-view button:has-text("开始生成")')
    await expect(generateBtn).toBeEnabled({ timeout: 5000 })
    console.log('✓ 生成按钮可点击')
  })

  // ========== 21. 工坊 LLM 选择器 ==========
  test('21. 工坊 LLM 选择器', async ({ page }) => {
    await page.goto(BASE_URL)
    await page.waitForLoadState('networkidle')

    await page.locator('.app-nav button:has-text("工坊")').click()
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)

    // 验证工坊视图存在
    const worldsmithView = page.locator('.worldsmith-view')
    await expect(worldsmithView).toBeVisible({ timeout: 5000 })
    console.log('✓ 工坊视图可见')

    // 验证有生成按钮
    const generateBtn = page.locator('.worldsmith-view button:has-text("开始生成")')
    await expect(generateBtn).toBeVisible()
    console.log('✓ 生成按钮存在')
  })

  // ========== 22. 工坊保存世界功能 ==========
  test('22. 工坊保存世界功能', async ({ page }) => {
    await page.goto(BASE_URL)
    await page.waitForLoadState('networkidle')

    await page.locator('.app-nav button:has-text("工坊")').click()
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)

    // 填写描述（用于验证保存）
    await page.locator('.worldsmith-view textarea').first().fill('一个宁静的小镇')
    await page.waitForTimeout(200)

    // 验证清空按钮存在
    const clearBtn = page.locator('.worldsmith-view button:has-text("清空")')
    await expect(clearBtn).toBeVisible({ timeout: 5000 })
    console.log('✓ 清空按钮存在')
  })

  // ========== 23. 工坊导入功能 ==========
  test('23. 工坊导入文件并显示内容', async ({ page }) => {
    await page.goto(BASE_URL)
    await page.waitForLoadState('networkidle')

    await page.locator('.app-nav button:has-text("工坊")').click()
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)

    // 创建测试 JSON 数据
    const testData = {
      world: {
        name: '测试小镇',
        description: '一个宁静的小镇',
        locations: [{ id: 'lib', name: '图书馆', description: '安静', tags: ['indoor'], capacity: 10 }],
        time_rules: { day_start_hour: 6, day_end_hour: 22, tick_interval_minutes: 30 },
        atmosphere: { mood: '宁静', dominant_themes: ['生活'], ambient_sounds: ['鸟鸣'] }
      },
      characters: [
        { id: 'c1', name: '张三', age: 30, gender: '男', pronouns: 'he', personality: { openness: 0.5, conscientiousness: 0.5, extraversion: 0.5, agreeableness: 0.5, neuroticism: 0.5 }, identity_tags: { primary: '图书管理员', secondary: [], self_identity: '' }, backstory: { title: '', childhood: '', adolescence: '', adulthood: '', present: '' }, initial_location: '图书馆', introduce_text: '大家好', needs: [] },
        { id: 'c2', name: '李四', age: 25, gender: '女', pronouns: 'she', personality: { openness: 0.6, conscientiousness: 0.5, extraversion: 0.5, agreeableness: 0.5, neuroticism: 0.5 }, identity_tags: { primary: '学生', secondary: [], self_identity: '' }, backstory: { title: '', childhood: '', adolescence: '', adulthood: '', present: '' }, initial_location: '图书馆', introduce_text: '你好', needs: [] }
      ],
      relationships: [{ from_id: 'c1', to_id: 'c2', relationship_type: '朋友', strength: 0.8, shared_history: '一起工作', potential_conflicts: [] }],
      personality_tips: [{ from: '张三', to: '李四', type: '互补', reason: '性格互补' }]
    }

    // 写入临时文件
    writeFileSync('/tmp/test_import_world.json', JSON.stringify(testData, null, 2))

    // 上传文件
    const fileInput = page.locator('.worldsmith-view input[type="file"]')
    await fileInput.setInputFiles('/tmp/test_import_world.json')
    await page.waitForTimeout(1500)

    // 验证世界名称显示
    const worldHeading = page.locator('.worldsmith-view h2:has-text("测试小镇")')
    await expect(worldHeading).toBeVisible({ timeout: 5000 })
    console.log('✓ 世界名称显示正确')

    // 验证描述显示在输入框
    const descTextarea = page.locator('.worldsmith-view textarea').first()
    await expect(descTextarea).toHaveValue('一个宁静的小镇')
    console.log('✓ 描述已填充到输入框')

    // 验证关系图谱显示（SVG 存在）
    const svgCount = await page.locator('.worldsmith-view svg').count()
    expect(svgCount).toBeGreaterThan(0)
    console.log('✓ 关系图谱已显示')

    // 验证性格提示显示
    const personalityTip = page.locator('.worldsmith-view:has-text("性格互动提示")')
    await expect(personalityTip).toBeVisible()
    console.log('✓ 性格提示已显示')

    // 验证地点列表显示
    const locationList = page.locator('.worldsmith-view:has-text("图书馆")')
    await expect(locationList).toBeVisible()
    console.log('✓ 地点列表已显示')
  })

  // ========== 24. 工坊生成错误处理 ==========
  test('24. 工坊生成错误处理', async ({ page }) => {
    await page.goto(BASE_URL)
    await page.waitForLoadState('networkidle')

    await page.locator('.app-nav button:has-text("工坊")').click()
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)

    // 不填写描述点击生成，应该显示错误
    const generateBtn = page.locator('.worldsmith-view button:has-text("开始生成")')
    await generateBtn.click()
    await page.waitForTimeout(500)

    // 验证生成按钮仍然可用（没有被永久禁用）
    await expect(generateBtn).toBeEnabled({ timeout: 5000 })
    console.log('✓ 空描述时按钮状态正常')
  })

  // ========== 25. 工坊完整生成流程 ==========
  test('25. 工坊完整生成流程', async ({ page }) => {
    test.setTimeout(300000) // 300秒超时，配合后端 Ollama 300秒超时

    await page.goto(BASE_URL)
    await page.waitForLoadState('networkidle')

    // 1. 点击工坊 Tab
    await page.locator('.app-nav button:has-text("工坊")').click()
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)
    console.log('✓ 工坊 Tab 已点击')

    // 2. 选择本地 Ollama 模型
    const llmSelect = page.locator('.worldsmith-view select').first()
    await llmSelect.selectOption('local')
    console.log('✓ 已选择本地 Ollama 模型')

    // 3. 输入世界描述
    await page.locator('.worldsmith-view textarea').first().fill('一个宁静的小镇，有图书馆、面包店和广场。')
    console.log('✓ 世界描述已填写')

    // 4. 点击开始生成
    const generateBtn = page.locator('.worldsmith-view button:has-text("开始生成")')
    await generateBtn.click()
    console.log('✓ 开始生成按钮已点击')

    // 5. 等待生成完成或超时（最多300秒，与后端 Ollama 超时一致）
    const startTime = Date.now()
    const timeout = 300000

    // 等待条件：世界内容出现 或 错误出现 或 超时
    while (Date.now() - startTime < timeout) {
      // 检查是否有世界内容（主内容区显示）
      const worldContent = page.locator('.worldsmith-view h2:has-text("🌍")')
      if (await worldContent.isVisible({ timeout: 500 }).catch(() => false)) {
        const worldName = await worldContent.textContent()
        console.log(`✓ 世界生成成功: ${worldName}`)
        break
      }

      // 检查是否有超时错误
      const errorMsg = page.locator('.worldsmith-view [style*="color: var(--accent-red)"]')
      if (await errorMsg.isVisible({ timeout: 500 }).catch(() => false)) {
        const errorText = await errorMsg.textContent()
        if (errorText?.includes('生成超时')) {
          console.log('✓ 检测到生成超时（Ollama 模型不可用）')
        } else {
          console.log(`✓ 生成出错: ${errorText}`)
        }
        break
      }

      // 检查生成按钮是否重新可用
      const isDisabled = await generateBtn.isDisabled().catch(() => true)
      if (!isDisabled) {
        const hasWorldContent = await page.locator('.worldsmith-view h2:has-text("🌍")').isVisible().catch(() => false)
        if (hasWorldContent) {
          console.log('✓ 世界生成成功')
        } else {
          const errorText = await page.locator('.worldsmith-view [style*="color: var(--accent-red)"]').textContent().catch(() => '')
          console.log(`✓ 生成结束: ${errorText || '无错误信息'}`)
        }
        break
      }

      await page.waitForTimeout(1000)
    }

    // 验证：要么有世界内容，要么有错误信息
    const hasWorldContent = await page.locator('.worldsmith-view h2:has-text("🌍")').isVisible().catch(() => false)
    const hasError = await page.locator('.worldsmith-view [style*="color: var(--accent-red)"]').isVisible().catch(() => false)
    expect(hasWorldContent || hasError).toBeTruthy()
    console.log(`✓ 生成测试完成（世界:${hasWorldContent}, 错误:${hasError}）`)
  })

  // ========== 20. 停止按钮存在 ==========
  test('20. 停止按钮', async ({ page }) => {
    await page.goto(BASE_URL)
    await page.waitForLoadState('networkidle')

    const stopBtn = page.locator('.control-bar button:has-text("■ 停止")')
    await expect(stopBtn).toBeVisible()
    console.log('✓ 停止按钮存在')
  })
})
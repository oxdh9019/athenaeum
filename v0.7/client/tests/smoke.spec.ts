/**
 * smoke.spec.ts — 烟雾测试（<30s，无需 LLM）
 *
 * 覆盖：服务器健康、前端加载、Tab 导航、TopBar/ControlBar/状态指示器、停止按钮。
 * 不启动世界、不创建角色、不生成内容——只验证 UI 骨架可用。
 *
 * 运行：npm run test:smoke
 * 前置：FastAPI 服务在 :8000，前端已 build（`v0.7/client/dist/index.html` 存在）。
 */

import { test, expect } from '@playwright/test'

const BASE_URL = 'http://localhost:8000'

test.describe('V0.7 Athenaeum 烟雾测试', () => {

  test('1. 服务器健康检查', async ({ request }) => {
    const response = await request.get(`${BASE_URL}/health`)
    expect(response.ok()).toBeTruthy()
    const json = await response.json()
    expect(json.status).toMatch(/^(healthy|degraded)$/)
    expect(json.version).toBe('0.7')
  })

  test('2. 前端页面加载', async ({ page }) => {
    await page.goto(BASE_URL)
    await page.waitForLoadState('networkidle')

    await expect(page).toHaveTitle(/Athenaeum/)
    await expect(page.locator('.app-header')).toBeVisible()
    await expect(page.locator('.app-logo h1')).toContainText('Athenaeum')
  })

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
    }
  })

  test('4. TopBar 显示', async ({ page }) => {
    await page.goto(BASE_URL)
    await page.waitForLoadState('networkidle')

    await expect(page.locator('.topbar')).toBeVisible()
    await expect(page.locator('.topbar-time')).toBeVisible()
    await expect(page.locator('.topbar-tick')).toBeVisible()
  })

  test('5. ControlBar 显示', async ({ page }) => {
    await page.goto(BASE_URL)
    await page.waitForLoadState('networkidle')

    await expect(page.locator('.control-bar')).toBeVisible()
    await expect(page.locator('.control-bar button:has-text("暂停")')).toBeVisible()
    await expect(page.locator('.control-bar button:has-text("■ 停止")')).toBeVisible()
  })

  test('6. 状态指示器', async ({ page }) => {
    await page.goto(BASE_URL)
    await page.waitForLoadState('networkidle')

    await expect(page.locator('.app-status')).toBeVisible()
    await expect(page.locator('.status-dot')).toBeVisible()
  })

  test('7. 停止按钮可见（不点击，不真退出服务）', async ({ page }) => {
    await page.goto(BASE_URL)
    await page.waitForLoadState('networkidle')

    const stopBtn = page.locator('.control-bar button:has-text("■ 停止")')
    await expect(stopBtn).toBeVisible()
  })
})

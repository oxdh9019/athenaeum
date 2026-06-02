/**
 * zh-CN.ts — 前端中文文案字典
 *
 * 为什么不用 i18n 库：项目目前只服务中文用户，引入 i18next/react-intl 会增加 ~50KB
 * bundle 与额外概念（locale provider、useTranslation），对单语项目是负担。
 *
 * 用法：`import { T } from '../constants/zh-CN'; <h1>{T.app.title}</h1>`
 *
 * 范围：本文件覆盖 App.tsx（Tab/Header）、Dashboard、TopBar、ControlBar、PossessMode
 * 中**用户最常看见**的字符串。其他组件（Worldsmith 927 行、DiaryView 等）仍保留
 * 内联中文；这些是表单/卡片正文，逐字串化收益低，统一改动时一并迁移。
 *
 * 后续扩展：若项目要支持英文，复制本文件为 `en-US.ts`，加上 `type Locale = 'zh-CN' | 'en-US'`
 * + `currentLocale` 上下文即可。
 */

export const T = {
  app: {
    title: '🏛️ Athenaeum',
    version: 'V0.7',
    statusConnected: '已连接',
    statusDisconnected: '未连接',
  },
  tabs: {
    dashboard: '📊 仪表盘',
    agents: '👥 角色',
    dialogue: '💬 对话',
    soul: '🔮 灵魂',
    worldsmith: '🔨 工坊',
    diary: '📔 日记',
    timeline: '📜 时间线',
    map: '🗺️ 地图',
    possess: '🎭 附身',
  },
  dashboard: {
    worldStatus: '世界状态',
    tick: 'Tick',
    time: '时间',
    agentCount: '角色数',
    locations: '地点',
    createWorld: '创建世界',
    startWorld: '启动世界',
    createAgent: '创建角色',
    agentName: '角色名',
    occupation: '职业',
    addAgent: '添加角色',
    activeAgents: '活跃角色',
    noAgents: '暂无角色',
    recentEvents: '最近 5 个事件',
    noEvents: '暂无事件',
    actionEmoji: '🎬',
    dialogueEmoji: '💬',
  },
  locations: {
    library: '图书馆',
    cafe: '咖啡厅',
    park: '公园',
  },
  agentsView: {
    list: '角色列表',
    emotionState: '情绪状态',
    currentGoal: '当前目标',
    noGoal: '无特定目标',
    progress: '进度',
    personality: '性格',
    selectAgent: '选择角色查看详情',
    unknownOccupation: '未知职业',
  },
  dialogueView: {
    selectAgentA: '选择角色 A',
    selectAgentB: '选择角色 B',
    startDialogue: '开始对话',
    between: '与',
  },
  soulView: {
    title: (name: string) => `${name} 的灵魂`,
    coreDesires: '核心欲望',
    innerConflict: '内在矛盾',
    subconsciousRules: '潜意识规则',
    noDesires: '暂无核心欲望',
    noConflict: '暂无矛盾描述',
    noRules: '无潜意识规则',
    selectPrompt: '选择角色查看灵魂配置',
  },
  mapView: {
    defaultLocationIcon: '📍',
  },
  possess: {
    defaultPrompt: '🎭 附身模式',
    hint: '输入你想让该角色说的话。',
    send: '发送',
    release: '解除附身',
  },
  controlBar: {
    pause: '暂停',
    resume: '继续',
    stop: '■ 停止',
  },
  errors: {
    networkError: '网络错误',
    parseError: '服务器响应无法解析',
    serverError: '服务器错误',
  },
} as const

export type Translations = typeof T

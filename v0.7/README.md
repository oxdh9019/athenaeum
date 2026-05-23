# V0.7 灵魂增强版

V0.7 是 Athenaeum 的灵魂增强版本，为 AI 角色注入"灵魂"。通过整合内在矛盾、潜意识规则、条件反思机制，让 AI 角色从被动响应转向主动生活。

## 核心新增功能

### 1. Soul 层（Step 0）
- **InnerConflict**：角色内在矛盾（如"渴望知识自由传播" vs "害怕古籍损毁"）
- **SubconsciousRule**：潜意识规则，触发时自动产生 micro_action
- **SoulConfig**：整合所有灵魂级配置

### 2. SubconsciousEngine（Step 4.5）
- 零 LLM 成本的 micro_action 生成
- 环境触发词匹配
- 冷却机制防止重复触发

### 3. 条件反思机制（Step 1.5）
- **drama_score** 评估：
  - 高情绪词检测（争吵、告白等）
  - 关系变化幅度
  - 叙事事件
- 当 drama_score >= 0.2 时触发归档（非固定 10 Tick）
- 生成**内心感悟**文本（角色主观反思）

### 4. StoryMode（Step 7.5）
- 有限 Tick 的故事运行
- 结束检测：最大 Tick、无高优先级目标、结束关键词
- 自动生成故事摘要

## 文件结构

```
v0.7/
├── server/
│   └── core/
│       ├── character_schema.py   # Soul/InnerConflict/SubconsciousRule 模型
│       ├── subconscious_engine.py # 潜意识规则匹配引擎
│       ├── story_mode.py          # 故事模式与结束检测
│       ├── memory_archiver.py     # 条件反思机制
│       ├── emotion_model.py       # (from v0.5)
│       ├── personality_filter.py   # (from v0.5)
│       ├── heartbeat_mode.py      # (from v0.5)
│       ├── goal_manager.py        # (from v0.5)
│       ├── daily_planner.py       # (from v0.5)
│       └── v07_agent.py           # 整合所有模块
├── tests/
│   └── test_v07_soul_system.py   # 灵魂系统测试
└── README.md
```

## 运行测试

```bash
cd v0.7
python tests/test_v07_soul_system.py
```

## 开发进度

- [x] Step 0: Soul 层扩展（InnerConflict, SubconsciousRule）
- [x] Step 1: GoalManager 整合内在矛盾
- [x] Step 1.5: 条件反思机制（drama_score 触发）
- [x] Step 2: DailyPlanner（日程规划）
- [x] Step 3: EmotionModel（情绪模型）
- [x] Step 4: PersonalityFilter（性格过滤规则）
- [x] Step 4.5: SubconsciousEngine（潜意识规则引擎）
- [x] Step 5: HeartbeatMode（心跳模式）
- [x] Step 6: V07Agent 整合
- [x] Step 7: DialogueEngine 微观动作注入
- [x] Step 7.5: StoryMode（故事模式）

## 验证清单

- [ ] 内在矛盾验证：检查角色生成的目标是否体现矛盾双方
- [ ] 潜意识规则：模拟触发词，检查 micro_action 输出
- [ ] 条件反思：运行世界，仅高戏剧性 Tick 触发归档
- [ ] 心跳模式：角色独处时观察 LLM 调用次数降低
- [ ] 情绪变化：社交成功/失败时情绪正确变化
- [ ] 微观动作：对话消息中随机出现 *动作* 描述
- [ ] 故事模式：启动有限 Tick 世界，验证自动结束
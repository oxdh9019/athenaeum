# Athenaeum

AI character social simulation platform — a group of AI characters with independent personalities live autonomously in a dynamic world, interacting and forming relationships.

## 概述

Athenaeum 是一个AI角色社交模拟平台，多个具有独立个性的AI角色在动态世界中自主生活、互动并形成关系。用户可以旁观或"附身"任何角色来驱动故事情节。

## 核心架构

| 组件 | 角色 |
|------|------|
| **WorldX** | 世界引擎 — 空间、时间、关系、事件广播 |
| **Zyantine** | 人格引擎 — 欲望、记忆、决策逻辑 |
| **Agent Mesh** | 社交网络 — 通过 NATS 的角色间通信 |
| **User Portal** | 用户界面 — 旁观模式、附身模式 |

## 版本历史

| 版本 | 名称 | 说明 |
|------|------|------|
| [v0.7](v0.7/README.md) | 灵魂增强版 | 为角色注入"灵魂" — 内在矛盾、潜意识规则、条件反思、故事模式 |
| v0.6 | 命运纺机·记忆织网 | 长期记忆归档、语义检索、遗忘曲线 |
| v0.5 | 情感共鸣 | 情绪系统、关系演化、需求驱动 |
| v0.4 | 世界脉动 | 多地点世界、Tick 调度、环境影响 |
| v0.3 | 涌现故事 | 双角色异步对话、关系进化、Possession 原型 |
| v0.2 | 你我之间 | 双角色基础交互、意图生成 |
| v0.1 | 灵魂火花 | 单角色 YAML 配置、CLI 对话、记忆 |

## 快速开始

```bash
# 运行 v0.7 服务器
cd v0.7/server
python server.py

# 访问 http://localhost:8000
```

## V0.7 灵魂增强版

核心功能：
- **Soul 层**：InnerConflict（内在矛盾）、SubconsciousRule（潜意识规则）
- **SubconsciousEngine**：零 LLM 成本的 micro_action 生成
- **条件反思机制**：drama_score 评估，仅高戏剧性对话触发归档
- **StoryMode**：有限 Tick 故事运行，自动结束检测与摘要生成
- **世界工坊**：自然语言生成世界+角色+关系+相性分析
- **25 个自动化 e2e 测试**覆盖所有核心功能

### V0.7 修复记录 (2024-05-24)

- ✅ 修复 `[THINK]/[SPEAK]` 标签导致的 JSON 解析失败
- ✅ 修复 `needs`、`identity_tags`、`appearance`、`social_background` 字段格式兼容性
- ✅ 修复 Tab 切换崩溃问题（`saveToStorage` 变量顺序错误）
- ✅ 修复工坊导入功能状态恢复
- ✅ 添加已生成世界列表（localStorage 持久化）
- ✅ 导出/导入/应用到引擎按钮默认可见

### 技术栈

- **前端**：React + TypeScript + Vite
- **后端**：FastAPI + Python 3.14
- **LLM**：Ollama (qwen3.5:4b) / MiniMax-M2.7
- **测试**：Playwright e2e

## 文档

- `SPEC.md` — 完整系统规格说明
- `athenaeum.md` — 项目概览与集成策略
- `Athenaeum 分阶段开发路线图.txt` — 分阶段交付路线图
- `Athenaeum 架构核心决策记录.txt` — 架构决策记录 (ADR)

## 时间系统

```
1 现实分钟 = 1 游戏小时
1 现实小时 = 1 游戏天
```

## 许可

MIT
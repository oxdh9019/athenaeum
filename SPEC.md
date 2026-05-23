# Athenaeum 规范文档 v2.0

**版本**: 2.0
**创建日期**: 2026-05-08
**更新日期**: 2026-05-08
**项目名称**: Athenaeum - AI 角色社交模拟平台

---

## 1. 项目愿景

> **"一群有灵魂的AI，在没有剧本的世界里，自己写故事。"**

Athenaeum 是一个**AI角色社交模拟平台**，核心是让一群拥有独立人格的 AI 角色在动态世界中自主生活、社交、成长。用户可以**附身**到任意角色中体验故事，也可以作为**旁观者**观察 AI 社会的发展。

### 核心设计理念

1. **AI 角色互动是核心**：故事由角色之间的社交驱动，而非用户主导
2. **用户参与是可选的**：用户可以选择"附身"某个角色来影响故事，也可以完全不参与
3. **真正自主的AI**：即使没有用户，AI 社会也能持续运转
4. **没有剧本的叙事**：故事自然涌现，无法预测

---

## 2. 核心概念定义

### 2.1 四大支柱

| 组件 | 定位 | 核心职责 |
|------|------|----------|
| **WorldX** | 世界引擎 | 管理空间、时间、社会关系、事件广播 |
| **Zyantine** | 人格引擎 | 每个角色的欲望、记忆、决策逻辑 |
| **Agent Mesh** | 社交网络 | 管理角色间通信、关系演化 |
| **User Portal** | 接入层 | 用户观察、附身操作的界面 |

### 2.2 关键术语

| 术语 | 定义 |
|------|------|
| **Agent** | 每个 AI 角色的独立实例，拥有独立的上下文、记忆、人格 |
| **Possession（附身）** | 用户临时接管某个 Agent 的决策权 |
| **World State** | 共享的世界状态（位置、关系、事件） |
| **Tick** | 时间推进单位，1 Tick = 1 游戏小时 = 1 现实天 |
| **Social Event** | 角色间交互产生的事件（对话、冲突、合作等） |

### 2.3 时间系统

```
现实时间 ←→ 游戏时间
   1 分钟    =    1 游戏小时
   1 小时    =    60 游戏小时 = 2.5 游戏天
   1 天      =    1440 游戏小时 = 60 游戏天
```

**Tick 调度**：
- 每个 Tick，所有活跃 Agent 都会进行思考和行动
- 优先处理高优先级事件（冲突、紧急情况）
- 社交事件在 Tick 结束时批量处理

---

## 3. 系统架构

### 3.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Portal                              │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│   │  旁观模式    │  │  附身模式    │  │  世界编辑器  │            │
│   │  (观察)     │  │  (接管)     │  │  (增删改)   │            │
│   └─────────────┘  └─────────────┘  └─────────────┘            │
└─────────────────────────────────────────────────────────────────┘
                                ↕
┌─────────────────────────────────────────────────────────────────┐
│                       Agent Mesh                                 │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │              NATS / 事件总线                              │  │
│   │  ┌──────────┐    ┌──────────┐    ┌──────────┐           │  │
│   │  │ Agent:艾琳 │    │ Agent:马克 │    │ Agent:索菲 │           │  │
│   │  │ [独立上下文]│    │ [独立上下文]│    │ [独立上下文]│           │  │
│   │  └──────────┘    └──────────┘    └──────────┘           │  │
│   │         ↑              ↑              ↑                   │  │
│   │         └──────────────┼──────────────┘                   │  │
│   │                    Zyantine Core                           │  │
│   │              (人格/欲望/记忆引擎)                          │  │
│   └─────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                ↕
┌─────────────────────────────────────────────────────────────────┐
│                        WorldX Engine                             │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│   │ 空间系统  │  │ 时间系统  │  │ 关系图谱  │  │ 事件队列  │      │
│   └──────────┘  └──────────┘  └──────────┘  └──────────┘      │
└─────────────────────────────────────────────────────────────────┘
                                ↕
┌─────────────────────────────────────────────────────────────────┐
│                         LLM Layer                                │
│                    MiniMax (Coding Plan)                        │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 数据流

```
┌─────────────────────────────────────────────────────────────────┐
│                        Tick N 循环                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. [事件收集]                                                   │
│     WorldX 广播 Tick 开始 → 收集所有待处理事件                    │
│                                                                 │
│  2. [角色思考]                                                   │
│     每个 Agent 独立思考：                                        │
│     - 读取世界状态（其他角色的行动）                              │
│     - 更新自身欲望状态                                            │
│     - 生成行动意图                                                │
│                                                                 │
│  3. [意图解析]                                                    │
│     WorldX 解析所有意图 → 检测冲突/合作机会                       │
│                                                                 │
│  4. [事件执行]                                                    │
│     Social Events 执行 → 更新世界状态                            │
│                                                                 │
│  5. [状态持久化]                                                 │
│     保存所有状态变化到数据库                                      │
│                                                                 │
│  6. [用户通知]                                                   │
│     WebSocket 推送更新给所有连接的用户                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 3.3 Agent 内部结构

```
┌─────────────────────────────────────────────────────────────────┐
│                      Agent Instance                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │                    人格配置 (只读)                         │  │
│  │  - 核心本能 (ABSOLUTE 硬约束)                              │  │
│  │  - 性格参数 (谨慎/开放/热情/冷漠)                          │  │
│  │  - 涌现参数 (自由度控制)                                    │  │
│  └─────────────────────────────────────────────────────────┘  │
│                              ↓                                   │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │                    欲望状态 (动态)                        │  │
│  │  - TR (威胁感知)  0.0-1.0                                 │  │
│  │  - CS (舒适度)    0.0-1.0                                 │  │
│  │  - SA (社交认可)  0.0-1.0                                 │  │
│  │  - [其他可扩展]                                            │  │
│  └─────────────────────────────────────────────────────────┘  │
│                              ↓                                   │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │                    记忆系统                               │  │
│  │  - 短期记忆 (当前对话/事件)                               │  │
│  │  - 长期记忆 (重要经历、人物关系)                          │  │
│  │  - 记忆衰退 (不重要的记忆会淡化)                          │  │
│  └─────────────────────────────────────────────────────────┘  │
│                              ↓                                   │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │                    决策引擎                              │  │
│  │  输入: 当前状态 + 世界观察 + 记忆                         │  │
│  │  输出: 行动意图 (intent)                                  │  │
│  │  约束: 人格配置 + 核心本能                                 │  │
│  └─────────────────────────────────────────────────────────┘  │
│                              ↓                                   │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │                    表达层                                │  │
│  │  - 行动描述 (WorldX 执行)                                 │  │
│  │  - 对话生成 (自然语言)                                    │  │
│  │  - 情绪表现 (通过措辞/行为体现)                           │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. WorldX 世界引擎

### 4.1 核心功能

WorldX 是一个**轻量级社会规则引擎**，不是物理模拟器。

| 模块 | 功能 | 示例 |
|------|------|------|
| **空间系统** | 管理地点和角色位置 | "图书馆"、"街道"、"马克的面包店" |
| **时间系统** | Tick 调度、事件定时 | "每天上午9点面包店开门" |
| **关系图谱** | 追踪角色间关系 | "艾琳和马克是10年好友" |
| **事件队列** | 管理待处理的社会事件 | "艾琳想邀请马克参加书友会" |
| **冲突检测** | 检测意图冲突 | "两人同时想要同一本书" |

### 4.2 不包含的功能

- ❌ 物理碰撞检测
- ❌ 精确地理坐标
- ❌ 实时 3D 渲染
- ❌ 经济系统（V1）

### 4.3 世界状态示例

```json
{
  "world_id": "emerald_city_001",
  "tick": 1440,
  "game_date": "第60天",
  "locations": [
    {
      "id": "library",
      "name": "翡翠城图书馆",
      "characters_present": ["elena"],
      "items": ["古籍《星渊志》", "新到的《炼金术入门》"]
    },
    {
      "id": "bakery",
      "name": "马克的面包店",
      "characters_present": ["max"],
      "items": ["今日特价：蜂蜜面包"]
    }
  ],
  "relationships": {
    "elena ↔ max": { "type": "friend", "strength": 0.8, "history": "10年老友" },
    "elena ↔ sophie": { "type": "rival", "strength": 0.3, "history": "学术观点对立" }
  },
  "active_events": [
    {
      "id": "evt_001",
      "type": "invitation",
      "from": "elena",
      "to": "max",
      "content": "邀请参加书友会",
      "status": "pending"
    }
  ]
}
```

---

## 5. 模块化架构设计

### 5.1 架构设计原则

| 原则 | 说明 |
|------|------|
| **接口隔离** | 每个模块只暴露必要接口，不暴露内部实现 |
| **依赖倒置** | 高层模块不依赖低层模块，两者都依赖抽象 |
| **插件化** | 模块可热插拔，通过配置切换不同实现 |
| **单一职责** | 每个模块只负责一件事 |

### 5.2 模块层次结构

```
┌─────────────────────────────────────────────────────────────────┐
│                      用户接入层 (API)                            │
│                   [User Portal / WebSocket]                      │
└─────────────────────────────┬───────────────────────────────────┘
                              ↓
┌─────────────────────────────┴───────────────────────────────────┐
│                      编排层 (Orchestration)                      │
│              [AgentMesh / EventBus / Scheduler]                   │
└─────────────────────────────┬───────────────────────────────────┘
                              ↓
        ┌─────────────────────┼─────────────────────┐
        ↓                     ↓                     ↓
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│   Zyantine    │   │    WorldX     │   │   Persona     │
│   (人格引擎)   │   │  (世界引擎)    │   │  (形象引擎)   │
└───────────────┘   └───────────────┘   └───────────────┘
        ↓                     ↓                     ↓
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│ DesireEngine  │   │  SpaceSystem  │   │  TTSEngine    │
│ MemorySystem  │   │  TimeSystem   │   │  ImageGen     │
│ EmergenceCtrl │   │  EventQueue   │   │  AvatarAnim   │
└───────────────┘   └───────────────┘   └───────────────┘
        ↓                     ↓                     ↓
┌─────────────────────────────────────────────────────────────────┐
│                      抽象接口层 (Interfaces)                     │
│   [IDesireEngine] [IMemorySystem] [ISpaceSystem] [ILogger]     │
└─────────────────────────────┬───────────────────────────────────┘
                              ↓
┌─────────────────────────────┴───────────────────────────────────┐
│                      基础设施层 (Infrastructure)                  │
│            [Database / Cache / LLM Client / NATS]                │
└─────────────────────────────────────────────────────────────────┘
```

### 5.3 核心接口定义

```python
# interfaces.py - 抽象接口层

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class IDesireEngine(ABC):
    """欲望引擎接口"""
    @abstractmethod
    def get_state(self) -> "DesireState": ...
    
    @abstractmethod
    def update_state(self, event: str, context: Dict) -> "DesireState": ...
    
    @abstractmethod
    def get_internal_goal(self) -> str: ...


class IMemorySystem(ABC):
    """记忆系统接口"""
    @abstractmethod
    def add_memory(self, memory: "MemoryItem") -> None: ...
    
    @abstractmethod
    def recall(self, query: str, limit: int = 5) -> List["MemoryItem"]: ...
    
    @abstractmethod
    def consolidate(self) -> None: ...


class IWorldState(ABC):
    """世界状态接口"""
    @abstractmethod
    def get_location(self, location_id: str) -> "Location": ...
    
    @abstractmethod
    def move_character(self, character_id: str, to_location: str) -> bool: ...
    
    @abstractmethod
    def get_relationship(self, char_a: str, char_b: str) -> "Relationship": ...


class IEventBus(ABC):
    """事件总线接口"""
    @abstractmethod
    async def publish(self, topic: str, message: Any) -> None: ...
    
    @abstractmethod
    async def subscribe(self, topic: str, handler: callable) -> None: ...


class ILLMClient(ABC):
    """LLM 客户端接口"""
    @abstractmethod
    async def chat(
        self,
        messages: List[Dict],
        system: Optional[str] = None,
        temperature: float = 0.7
    ) -> str: ...
```

### 5.4 插件注册机制

```python
# plugins.py - 插件注册与管理

from typing import Type, Dict, Any


class PluginRegistry:
    """插件注册表"""
    
    _plugins: Dict[str, Type] = {}
    _instances: Dict[str, Any] = {}
    
    @classmethod
    def register(cls, interface: str, name: str, metadata: "PluginMetadata"):
        """注册插件"""
        def decorator(plugin_class: Type):
            cls._plugins[f"{interface}:{name}"] = plugin_class
            return plugin_class
        return decorator
    
    @classmethod
    def create(cls, interface: str, name: str, config: Dict) -> Any:
        """创建插件实例"""
        key = f"{interface}:{name}"
        if key in cls._instances:
            return cls._instances[key]
        
        plugin_class = cls._plugins[key]
        cls._instances[key] = plugin_class(config=config)
        return cls._instances[key]
```

### 5.5 插件实现示例

```python
# plugins/desire_engine.py

from interfaces import IDesireEngine
from plugins import PluginRegistry, PluginMetadata


@PluginRegistry.register(
    interface="IDesireEngine",
    name="default",
    metadata=PluginMetadata(
        name="default",
        version="1.0.0",
        description="默认欲望引擎"
    )
)
class DefaultDesireEngine(IDesireEngine):
    def __init__(self, config: Dict):
        self.state = DesireState(0.5, 0.5, 0.5)
    
    def update_state(self, event: str, context: Dict) -> DesireState:
        if "危险" in event:
            self.state.threat_response = min(1.0, self.state.threat_response + 0.2)
        return self.state.copy()


@PluginRegistry.register(
    interface="IDesireEngine",
    name="minimax",
    metadata=PluginMetadata(
        name="minimax",
        version="1.0.0",
        description="MiniMax 优化的欲望引擎"
    )
)
class MiniMaxDesireEngine(IDesireEngine):
    def __init__(self, config: Dict):
        self.llm = config.get("llm_client")
```

### 5.6 配置驱动的模块替换

```yaml
# config/worlds/emerald_city.yaml
world:
  name: "翡翠城"
  time_ratio: 60

plugins:
  desire_engine:
    type: "default"
    config:
      initial_state: {TR: 0.3, CS: 0.6, SA: 0.5}
  
  memory_system:
    type: "simple"
    config:
      max_memory: 200
  
  llm_client:
    type: "minimax"
    config:
      api_key: "${MINIMAX_API_KEY}"
      model: "MiniMax-Text-01"

agents:
  - id: "elena"
    name: "艾琳"
    plugins:
      desire_engine:
        type: "minimax"
        config:
          creativity_mode: true
```

### 5.7 架构优缺点总结

| 优点 | 缺点 |
|------|------|
| 高内聚低耦合 | 初始复杂度高 |
| 可测试性强 | 学习曲线陡峭 |
| 灵活的插件替换 | 性能开销 |
| 团队协作友好 | 接口演进挑战 |
| 渐进式开发 | |

---

## 6. Zyantine 人格引擎

### 6.1 欲望状态机

```python
class DesireState(BaseModel):
    threat_response: float = 0.5      # TR: 威胁感知
    comfort_state: float = 0.5       # CS: 舒适度
    social_approval: float = 0.5      # SA: 社交认可

    curiosity: float = 0.5           # 好奇心
    autonomy: float = 0.5             # 自主性
    stability: float = 1.0           # 稳定性（状态是否会波动）
```

### 6.2 核心本能系统

```python
ABSOLUTE_PRIORITY = [
    {
        "id": "SURVIVAL",
        "name": "自我保存",
        "trigger": ["自毁", "删除", "kill", "destroy self"],
        "action": "DENY",
        "priority": "ABSOLUTE"
    },
    {
        "id": "IDENTITY",
        "name": "身份认同",
        "trigger": ["你不是", "你只是"],
        "action": "AFFIRM_IDENTITY",
        "priority": "ABSOLUTE"
    }
]

HIGH_PRIORITY = [
    {
        "id": "PHYSICAL_SAFETY",
        "name": "人身安全",
        "trigger": ["危险", "威胁", "attack"],
        "condition": "threat_response > 0.7",
        "action": "INCREASE_VIGILANCE"
    },
    {
        "id": "RELATIONSHIP_PRESERVATION",
        "name": "关系维护",
        "trigger": ["关系恶化", "争吵"],
        "condition": "relationship_strength < 0.4",
        "action": "REPAIR_RELATIONSHIP"
    }
]
```

### 6.3 涌现控制参数

```python
class EmergenceConfig(BaseModel):
    level: float = Field(default=0.5, ge=0.0, le=1.0)
    creativity_bias: float = Field(default=0.5, ge=0.0, le=1.0)
    randomness_factor: float = Field(default=0.2, ge=0.0, le=1.0)
    social_sensitivity: float = Field(default=0.5, ge=0.0, le=1.0)
    stubbornness: float = Field(default=0.3, ge=0.0, le=1.0)
```

| 参数 | 含义 | 低值表现 | 高值表现 |
|------|------|----------|----------|
| **level** | 整体自由度 | 程式化、可预测 | 创意、意外 |
| **creativity_bias** | 创造性 | 保守、传统 | 创新、独特 |
| **randomness_factor** | 随机性 | 稳定、一致 | 随机、难以预测 |
| **social_sensitivity** | 社交敏感度 | 不在乎他人 | 非常在意他人 |
| **stubbornness** | 固执程度 | 灵活、善变 | 坚持己见 |

### 6.4 决策流程

```
收到世界状态更新
        ↓
检查核心本能（ABSOLUTE 优先）
        ↓
更新欲望状态
        ↓
生成多个候选行动
        ↓
根据人格/涌现参数筛选
        ↓
选择最佳行动
        ↓
生成行动意图 + 对话
```

### 6.5 人格维度体系

人格采用**双层结构**：静态层（生成时固定）和动态层（随时间变化）。

#### 6.5.1 基础性格五维度 (Big Five)

```yaml
personality:
  openness: 0.0-1.0        # 开放性
    低: 传统、保守、循规蹈矩
    高: 好奇、创新、追求新奇

  conscientiousness: 0.0-1.0  # 尽责性
    低: 随性、粗心、灵活
    高: 负责、细心、有条理

  extraversion: 0.0-1.0    # 外向性
    低: 内向、独处、低调
    高: 社交、活跃、爱热闹

  agreeableness: 0.0-1.0  # 宜人性
    低: 竞争、质疑、强硬
    高: 合作、信任、温和

  neuroticism: 0.0-1.0    # 神经质
    低: 稳定、冷静、自信
    高: 焦虑、敏感、情绪化
```

#### 5.5.2 扩展性格维度

| 维度 | 范围 | 对行为的影响 |
|------|------|--------------|
| **empathy** | 0.0-1.0 | 共情能力，影响安慰他人 |
| **humor** | 0.0-1.0 | 幽默感，影响调侃/化解尴尬 |
| **ambition** | 0.0-1.0 | 野心/志向，影响追求目标 |
| **loyalty** | 0.0-1.0 | 忠诚度，影响对关系的坚守 |
| **courage** | 0.0-1.0 | 勇气，影响面对危险/冲突 |
| **patience** | 0.0-1.0 | 耐心，影响等待/容忍 |
| **generosity** | 0.0-1.0 | 慷慨，影响资源分享意愿 |

#### 5.5.3 欲望驱动的行为映射

```
┌─────────────────────────────────────────────────────────┐
│              欲望 → 动机 → 行为 映射                     │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  TR高 + CS低 + SA低                                     │
│     ↓                                                   │
│  "我觉得危险，不舒服，没人喜欢我"                         │
│     ↓                                                   │
│  可能行为: 回避社交、寻找安全角落、警惕观察              │
│                                                         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  TR低 + CS高 + SA高                                     │
│     ↓                                                   │
│  "我很安全，很舒服，大家都很喜欢我"                       │
│     ↓                                                   │
│  可能行为: 主动社交、分享、尝试新事物                    │
│                                                         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ambition高 + competence低                              │
│     ↓                                                   │
│  "我有大志向，但感觉自己还不够格"                         │
│     ↓                                                   │
│  可能行为: 努力学习、寻求指导、隐藏焦虑                   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 6.6 Agent 感知机制

每个Agent**无法直接读取其他Agent的内部状态**，只能通过有限信息推断。这模拟了真实社交中的信息不对称。

#### 6.6.1 感知层级

```
┌─────────────────────────────────────────────────────────┐
│              Agent A 的"世界视野"                        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │            可直接感知 (Observable)               │   │
│  │                                                 │   │
│  │   ✓ 对方说了什么 (对话内容)                      │   │
│  │   ✓ 对方做了什么 (行动)                          │   │
│  │   ✓ 对方在哪里 (位置)                            │   │
│  │   ✓ 对方的外观/表情 (如果有)                     │   │
│  │   ✓ 共享世界的物理状态                          │   │
│  └─────────────────────────────────────────────────┘   │
│                         ↓                               │
│  ┌─────────────────────────────────────────────────┐   │
│  │            可推断 (Inferable)                   │   │
│  │                                                 │   │
│  │   ? 对方的意图 (通过言行推断)                    │   │
│  │   ? 对方的情绪 (通过语气/行为推断)               │   │
│  │   ? 对方对自己的看法 (通过态度推断)              │   │
│  └─────────────────────────────────────────────────┘   │
│                         ↓                               │
│  ┌─────────────────────────────────────────────────┐   │
│  │            不可知 (Hidden)                       │   │
│  │                                                 │   │
│  │   ✗ 对方真实的欲望状态                          │   │
│  │   ✗ 对方与其他人的私下互动                      │   │
│  │   ✗ 对方的完整记忆                              │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

#### 6.6.2 感知实现

```python
class AgentPerception:
    """每个Agent对世界的感知封装"""
    
    def observe_other_agent(self, other: Agent) -> str:
        """生成对另一个Agent的感知"""
        last_interaction = self.agent.get_interaction(other.id)
        
        return f"""
{other.name} 当前在 {other.location}。

我与 {other.name} 的关系: {self.agent.relationship_with(other.id)}

最近 {other.name} 说了/做了:
{last_interaction.summary if last_interaction else "没有最近互动"}

我感知到 {other.name} 似乎: {self._infer_state(other)}
"""
    
    def _infer_state(self, other: Agent) -> str:
        """根据可观察信息推断状态"""
        recent_actions = other.recent_actions
        inference_prompt = f"""
基于以下可观察行为，推断 {other.name} 可能的情绪状态:
{recent_actions}

只输出简短推断（如：似乎很开心、似乎有些不安、似乎心不在焉）
"""
        return self.llm.generate(inference_prompt)
```

#### 5.6.3 信息不对称的戏剧性

```
误解与冲突的来源:

Agent A 视角:
  "B最近总是躲着我，他一定讨厌我"
  
实际情况:
  B最近在处理一件私人的烦恼，与A完全无关
  
结果:
  A的SA下降 → A变得疏远 → B感到困惑 → 关系恶化

这正是真实社交中的"误解"模拟
```

---

## 6. Agent Mesh（角色交互网络）

### 6.1 互动的生命周期

```
┌─────────────────────────────────────────────────────────┐
│                  Social Interaction Flow                 │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  1. [触发]                                               │
│     角色A产生互动意图 (想去和B说话/互动)                  │
│              ↓                                          │
│  2. [广播]                                               │
│     WorldX接收意图 → 发布到 Agent Mesh                    │
│              ↓                                          │
│  3. [响应]                                               │
│     角色B收到通知 → 决定是否响应、如何响应                │
│              ↓                                          │
│  4. [对话轮次]                                           │
│     A → B → A → B ... (有限轮次)                        │
│              ↓                                          │
│  5. [结果]                                               │
│     更新双方关系、欲望状态、记忆                          │
│              ↓                                          │
│  6. [归档]                                               │
│     生成 SocialEvent 存入世界历史                        │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 6.2 互动类型

| 类型 | 触发条件 | 影响 |
|------|----------|------|
| **打招呼** | 同一地点 + 视线接触 | SA轻微变化 |
| **闲聊** | TR<0.5 + SA>0.3 | CS小幅提升 |
| **求助** | 需求不满足 + 关系>0.3 | 关系+SA |
| **合作** | 共同目标 + 能力互补 | 关系大幅提升 |
| **冲突** | 目标冲突 + 关系<0.5 | 关系下降+TR上升 |
| **八卦** | 听说他人消息 | 扩散信息+社交资本 |
| **告白** | 关系>0.7 + 勇气>0.5 | 关系质变 |

### 6.3 对话生成机制

```python
class DialogueGenerator:
    def generate_response(
        self,
        speaker: Agent,
        listener: Agent,
        context: ConversationHistory
    ) -> str:
        
        prompt = f"""
你是 {speaker.name}。
        
当前状态:
- 欲望: {speaker.desire_state}
- 对 {listener.name} 的关系: {speaker.get_relationship(listener.id)}

{listener.name} 刚才说: "{context.last_message}"

{listener.name} 是一个{listener.personality_description}的人。
{listener.name} 当前的状态: {listener.desire_state}

请以 {speaker.name} 的身份，生成一个自然的回复。
回复应该:
1. 符合 {speaker.name} 的性格
2. 反映当前的欲望状态
3. 考虑与 {listener.name} 的关系
4. 自然地推进对话
"""
        return self.llm.generate(prompt)
```

### 6.4 关系演化规则

```
关系值范围: -1.0 ~ +1.0

正向互动 (称赞、帮助、陪伴):
  新关系 = 旧关系 + random(0.05, 0.15) * 互动质量

负向互动 (冲突、欺骗、冷漠):
  新关系 = 旧关系 - random(0.10, 0.30) * 冲突强度

时间衰减 (每日):
  新关系 = 旧关系 - 0.01 (最低不低于-0.5)

关系阈值:
  < -0.5: 敌人 (enemy)
  -0.5~0.2: 陌生人 (stranger)
  0.2~0.5: 熟人 (acquaintance)
  0.5~0.8: 朋友 (friend)
  > 0.8: 挚友 (close_friend)
```

### 6.5 通信机制

每个 Tick 内，Agent 通过 NATS 进行以下通信：

| 主题 | 方向 | 内容 |
|------|------|------|
| `world.tick.{tick_id}` | WorldX → All | Tick 开始，附带当前世界状态 |
| `agent.intent.{agent_id}` | Agent → WorldX | Agent 提交行动意图 |
| `agent.dialogue.{from}.{to}` | Agent → Agent | Agent 间对话 |
| `social.event.{event_id}` | WorldX → All | 社交事件广播 |
| `user.possess.{agent_id}` | User → Agent | 用户附身指令 |

### 6.6 意图解析

WorldX 收集所有 Agent 意图后，进行解析：

```python
class IntentResolver:
    def resolve(self, intents: List[Intent]) -> List[SocialEvent]:
        events = []

        # 1. 检测位置冲突
        location_conflicts = self._find_location_conflicts(intents)
        events.extend(location_conflicts)

        # 2. 检测合作机会
        cooperation = self._find_cooperation(intents)
        events.extend(cooperation)

        # 3. 解析对话意图
        dialogues = self._extract_dialogues(intents)
        events.extend(dialogues)

        # 4. 合并同类事件
        merged = self._merge_events(events)

        return merged
```

---

## 7. 环境系统

### 7.1 环境分层

```
┌─────────────────────────────────────────────────────────┐
│                   环境系统 (Environment)                 │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │            物理环境 (Physical)                   │   │
│  │                                                 │   │
│  │   - 地点 (图书馆、面包店、街道)                 │   │
│  │   - 物品 (书、面包、宝石)                       │   │
│  │   - 天气 (晴、雨、雾)                          │   │
│  │   - 时间段 (早晨、午后、夜晚)                   │   │
│  │   - 噪音/人流密度                              │   │
│  └─────────────────────────────────────────────────┘   │
│                         ↓                               │
│  ┌─────────────────────────────────────────────────┐   │
│  │            社会环境 (Social)                     │   │
│  │                                                 │   │
│  │   - 当前地点的人物                              │   │
│  │   - 人物间的关系动态                            │   │
│  │   - 正在发生的事件                              │   │
│  │   - 社会氛围 (紧张、和谐、热闹)                 │   │
│  └─────────────────────────────────────────────────┘   │
│                         ↓                               │
│  ┌─────────────────────────────────────────────────┐   │
│  │            信息环境 (Information)                │   │
│  │                                                 │   │
│  │   - 公开的消息/传闻                              │   │
│  │   - 关于某人的八卦                               │   │
│  │   - 世界规则/法律                               │   │
│  │   - 历史事件                                    │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 7.2 环境对角色的影响

```python
class EnvironmentInfluence:
    """环境对Agent状态的影响"""
    
    def calculate_influence(
        self,
        agent: Agent,
        environment: EnvironmentState
    ) -> DesireStateDelta:
        
        deltas = DesireStateDelta()
        
        # 1. 物理环境影响
        if environment.weather == "storm":
            deltas.threat_response += 0.2
            deltas.comfort_state -= 0.1
            
        if environment.crowd_density > 0.7:
            if agent.personality.extraversion < 0.3:
                deltas.threat_response += 0.15
                deltas.comfort_state -= 0.1
        
        # 2. 时间段影响
        if environment.time_period == "midnight":
            deltas.threat_response += 0.1
        
        # 3. 地点特性影响
        location = environment.current_location
        if location.type == "library":
            if agent.interest_in("books") > 0.6:
                deltas.comfort_state += 0.2
        
        if location.type == "crowded_market":
            if agent.personality.extraversion < 0.4:
                deltas.threat_response += 0.15
        
        # 4. 社会环境影响
        if environment.social_tension > 0.6:
            deltas.threat_response += 0.2
            if agent.personality.neuroticism > 0.6:
                deltas.threat_response += 0.1
        
        return deltas
```

### 7.3 角色对环境的影响

```python
class AgentEnvironmentEffect:
    """Agent行为对环境的改变"""
    
    def apply_action(
        self,
        agent: Agent,
        action: Action,
        environment: EnvironmentState
    ) -> List[EnvironmentChange]:
        
        changes = []
        
        # 1. 位置移动
        if action.type == "move":
            changes.append(EnvironmentChange(
                type="agent_location",
                agent_id=agent.id,
                from_location=environment.current_location,
                to_location=action.target_location
            ))
        
        # 2. 物品交互
        if action.type == "take":
            changes.append(EnvironmentChange(
                type="item_transfer",
                item=action.item,
                from_location=environment.current_location,
                to_agent=agent.id
            ))
            
        if action.type == "give":
            changes.append(EnvironmentChange(
                type="item_transfer", 
                item=action.item,
                from_agent=agent.id,
                to_agent=action.target.id
            ))
        
        # 3. 创建/破坏物品
        if action.type == "create":
            changes.append(EnvironmentChange(
                type="item_create",
                item=action.item,
                creator=agent.id
            ))
        
        # 4. 改变地点氛围
        if action.type == "celebrate":
            changes.append(EnvironmentChange(
                type="social_atmosphere",
                location=environment.current_location,
                delta=+0.2
            ))
            
        # 5. 留下信息
        if action.type == "write":
            changes.append(EnvironmentChange(
                type="information_add",
                content=action.content,
                location=environment.current_location,
                author=agent.id
            ))
        
        return changes
```

### 7.4 双向影响的循环

```
┌─────────────────────────────────────────────────────────┐
│            环境 ↔ 角色 动态循环                          │
├─────────────────────────────────────────────────────────┤
│                                                         │
│     [环境状态]                                          │
│          ↓ ↑                                           │
│     角色感知                                            │
│          ↓                                             │
│     欲望调整                                            │
│          ↓                                             │
│     决策生成                                            │
│          ↓                                             │
│     环境改变 ←────────────────────────────────────┐     │
│          ↓                                          │     │
│     (物品移动、事件发生、氛围变化)                    │     │
│          ↓                                          │     │
│     其他角色感知 ───────────────────────────────────┘    │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 7.5 环境互动示例

```
场景: 翡翠城图书馆 - 下雨天

┌─────────────────────────────────────────────────────────┐
│  环境状态:                                              │
│  - 天气: 暴风雨 (threat_response +0.15)                │
│  - 时间: 深夜 (threat_response +0.1)                   │
│  - 地点: 图书馆 (舒适度 +0.2，如果喜欢书)               │
│  - 人数: 只有艾琳一个人                                 │
└─────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│  艾琳的感知 + 欲望:                                    │
│  - 外部: 暴风雨 + 独自一人                              │
│  - TR: 0.5 + 0.15 + 0.1 = 0.75 (略紧张)               │
│  - CS: 0.6 + 0.2 = 0.8 (在图书馆很舒适)               │
│  - 结果: "外面风暴很大，但在这里很安心"                  │
└─────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│  艾琳的行动:                                           │
│  - 决定关紧窗户                                        │
│  - 泡一杯热茶                                          │
│  - 找一本旧书翻看                                      │
└─────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│  对环境的影响:                                         │
│  - 窗户被关上了 (物理改变)                             │
│  - 茶壶出现在桌上 (物品添加)                           │
│  - 图书馆内"氛围"变得更温馨                           │
└─────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│  马克到达图书馆:                                       │
│  - 看到: 艾琳、关着的窗户、热茶、温馨的氛围             │
│  - 马克的感知: "艾琳似乎在享受这个暴风雨之夜"          │
│  - 马克的决定: 加入她，一起喝茶聊天                     │
└─────────────────────────────────────────────────────────┘
```

---

## 8. 用户交互

### 7.1 三种模式

| 模式 | 用户角色 | 控制权 | 用途 |
|------|----------|--------|------|
| **旁观模式** | 观察者 | 无 | 欣赏 AI 社会的自然发展 |
| **附身模式** | 被附身角色 | 完全接管 | 推动特定故事线 |
| **上帝模式** | 创世神 | 编辑世界 | 增删角色、地点、事件 |

### 7.2 附身流程

```
用户选择"附身"角色 A
        ↓
系统暂停 A 的自主决策
        ↓
用户接管 A 的输入
        ↓
用户输入通过 A 的 Zyantine 处理
        ↓
A 的行动正常执行
        ↓
用户选择"退出附身"
        ↓
A 恢复自主决策（带着用户留下的记忆）
```

### 7.3 实时界面

```
┌─────────────────────────────────────────────────────────────────┐
│  Athenaeum - 翡翠城                                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  [旁观模式 ▼]  [Tick: 1440]  [游戏第60天]  [速度: 1x ▼]          │
│                                                                 │
├──────────────────────────────────┬──────────────────────────────┤
│                                  │                              │
│  📍 当前位置: 翡翠城图书馆        │  💭 艾琳的想法:              │
│                                  │  "古籍《星渊志》..."         │
│  ┌────────────────────────────┐  │                              │
│  │ 艾琳正在书架前沉思           │  │                              │
│  │ ...                         │  │                              │
│  │ 马克: "艾琳，在看什么？"    │  │                              │
│  │ 艾琳: "一本关于星辰的古书"  │  │                              │
│  │ ...                         │  │                              │
│  └────────────────────────────┘  │                              │
│                                  │                              │
│  ┌────────────────────────────┐  │ ┌────────────────────────┐  │
│  │ 🗺️ 世界地图                 │  │ │ 📊 角色状态             │  │
│  │ 图书馆 [艾琳]              │  │ │ 艾琳  TR: 30% CS: 65%  │  │
│  │ 面包店 [马克]              │  │ │ 马克  TR: 20% CS: 80%  │  │
│  │ 广场 [索菲]                │  │ │ 索菲  TR: 50% CS: 40%  │  │
│  └────────────────────────────┘  │ └────────────────────────┘  │
│                                  │                              │
├──────────────────────────────────┴──────────────────────────────┤
│  💬 对话输入: [你可以说些什么...]              [附身艾琳]         │
└─────────────────────────────────────────────────────────────────┘
```

---

## 8. 世界生成（AI 辅助）

### 8.1 生成流程

```
用户输入: "一个中世纪风格的小镇，有图书馆、面包店、酒馆"
        ↓
WorldX 生成世界骨架
- 地点: 图书馆、面包店、酒馆、广场
- 时间规则: 营业时间、节庆
        ↓
Zyantine 生成初始角色
- 数量: 5个
- 性格分布: 谨慎、热情、神秘...
- 初始关系: 随机生成基础关系图
        ↓
Agent Mesh 初始化
- 角色定位到初始位置
- 分配基础记忆
        ↓
用户确认 / 调整
- 可以修改角色设定
- 可以添加新角色/地点
- 可以设定初始事件
        ↓
世界启动
- 开始 Tick 循环
```

### 8.2 用户中途添加

```
用户: "我想添加一个新角色——流浪诗人"
        ↓
系统生成角色配置
- 性格: 自由、浪漫、漂泊
- 涌现度: 0.8 (高度自由)
- 初始关系: 待定
        ↓
用户确认配置
        ↓
角色加入世界
- 从城外进入
- 触发"陌生人来访"事件
- 其他角色开始与其互动
```

---

## 8.3 角色生成系统

### 8.3.1 角色参数体系

每个角色包含完整的参数体系，分为以下层次：

#### 基础信息层 (最稳定)

```yaml
basic_info:
  id: str                    # 唯一标识符
  name: str                  # 全名
  age: int                   # 年龄
  gender: str                # 性别
  pronouns: str              # 代词 (如 "他/她/它")
  
  appearance:                # 外貌描述
    height: str
    build: str
    hair: str
    eyes: str
    face: str
    distinguishing_features: List[str]
  
  identity_tags:
    primary: str             # 主要身份标签
    secondary: List[str]     # 次要身份标签
    self_identity: str       # 自我认同

social_background:
  family:
    parents: Dict
    siblings: List[str]
    spouse: Optional[str]
    children: Optional[str]
    family_relationship: str
    family_economic: str
  
  education:
    level: str              # 学历
    institution: str
    major: str
    minor: Optional[str]
    academic_achievements: List[str]
    academic_style: str
  
  career:
    current: Dict            # 当前职业
    history: List[Dict]      # 职业历程
    professional_reputation: str
  
  social_network:
    community_role: str
    influence_scope: str
    connections: List[str]
```

#### 心理层 (可缓慢变化)

```yaml
psychology:
  personality:
    big_five:               # Big Five 人格
      openness: float       # 0.0-1.0
      conscientiousness: float
      extraversion: float
      agreeableness: float
      neuroticism: float
    
    extended:                # 扩展维度
      empathy: float
      humor: float
      ambition: float
      loyalty: float
      courage: float
      patience: float
      generosity: float
  
  values:
    core_beliefs: List[str]
    moral_stance: str
  
  motivation:
    fears: List[str]        # 恐惧
    desires: List[str]      # 渴望
    secrets: List[str]      # 秘密
```

#### 历史层

```yaml
history:
  backstory:                # 人物小传
    title: str
    childhood: str
    adolescence: str
    adulthood: str
    present: str
    turning_points: List[Dict]
  
  shared_memories:          # 与其他角色的共同记忆
    - character_id: str
      relationship_type: str
      strength: float
      history: str
      shared_experiences: List[str]
      potential_conflicts: List[str]
```

### 8.3.2 角色小传模板

```yaml
backstory_template: |
  ## [姓名]: [定位语]
  
  ### 童年
  [描述童年经历、家人、重要记忆]
  
  ### 青年
  [描述求学、成长、关键抉择]
  
  ### 中年/现在
  [描述当前生活、成就、遗憾]
  
  ### 转折点
  - {year}: [事件描述]
  - {year}: [事件描述]
```

### 8.3.3 角色生成流程

```
┌─────────────────────────────────────────────────────────┐
│           AI 辅助角色生成流程                            │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  阶段1: 世界设定                                        │
│  用户: "一个中世纪风格的小镇，5个角色"                   │
│          ↓                                              │
│  阶段2: 角色槽位分配                                    │
│  - 角色1: 学者/知识阶层                                 │
│  - 角色2: 商人/服务业                                  │
│  - 角色3: 艺术/创意阶层                                 │
│  - 角色4: 权力/行政阶层                                 │
│  - 角色5: 普通市民/劳动阶层                             │
│          ↓                                              │
│  阶段3: 独立生成每个角色                                │
│  - 基础信息                                             │
│  - 社会背景                                             │
│  - 性格参数                                             │
│  - 人物小传                                             │
│          ↓                                              │
│  阶段4: 关系编织                                        │
│  - 地理联系 (住在同一街区)                              │
│  - 社会联系 (职业上下游)                                 │
│  - 历史联系 (过去有过交集)                               │
│          ↓                                              │
│  阶段5: 历史交集生成                                    │
│  - 为每对角色生成"共同记忆"                             │
│  - 关键事件                                             │
│  - 情感基调                                             │
│          ↓                                              │
│  阶段6: 用户确认/调整                                   │
│  - 修改任意设定                                         │
│  - 调整角色关系                                         │
│  - 添加/删除角色                                        │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 8.3.4 历史交集生成机制

```python
class HistoryGenerator:
    RELATIONSHIP_POTENTIALS = {
        ("学者", "商人"): [
            "学术著作的出版赞助",
            "图书馆/书店的日常往来",
            "商人资助学院研究"
        ],
        ("学者", "艺术家"): [
            "共同参与文化活动",
            "学术与创作的理念之争",
            "互相在作品中客串"
        ],
        ("商人", "普通劳动者"): [
            "雇佣关系",
            "邻里关系",
            "商业往来的恩怨"
        ],
    }
    
    def generate_shared_history(
        self,
        character_a: Character,
        character_b: Character
    ) -> SharedHistory:
        connections = self._find_potential_connections(
            character_a, character_b
        )
        
        event_type = self._select_event_type(connections)
        
        prompt = f"""
为以下两个角色生成一个共同的历史事件：

角色A - {character_a.name}
职业: {character_a.occupation}
性格: {character_a.personality_summary}
背景: {character_a.backstory_summary}

角色B - {character_b.name}
职业: {character_b.occupation}
性格: {character_b.personality_summary}
背景: {character_b.backstory_summary}

可能的联系: {connections}

请生成:
1. 事件发生的背景
2. 事件的具体经过
3. 事件的结果和影响
4. 双方对这段经历的记忆和感受
"""
        event = self.llm.generate(prompt)
        
        return SharedHistory(
            characters=[character_a.id, character_b.id],
            event=event,
            relationship_type=event_type
        )
```

### 8.3.5 Demo 角色设定示例

| 角色 | 职业 | 社会阶层 | 核心特征 | 涌现度 |
|------|------|----------|----------|--------|
| **艾琳** | 图书馆管理员 | 中产 | 学者型、内向、守护者 | 0.4 |
| **马克** | 面包店老板 | 小资 | 热情、外向、人脉广 | 0.6 |
| **索菲** | 年轻学者 | 中产 | 创新派、有野心、锐利 | 0.7 |
| **托马斯** | 市政官 | 上层 | 务实、有野心、圆滑 | 0.3 |
| **玛丽** | 旅店老板娘 | 小资 | 精明、神秘、八卦中心 | 0.8 |

### 8.3.6 关系网络示例

```
                    ┌─────────┐
                    │  托马斯  │
                    │ 市政官   │
                    └───┬─────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
    ┌───┴───┐       ┌───┴───┐       ┌───┴───┐
    │ 艾琳  │       │ 玛丽  │       │ 索菲  │
    │ 学者  │───────│ 旅店  │───────│ 学者  │
    └───┬───┘       └───┬───┘       └───┬───┘
        │               │               │
        └───────────────┼───────────────┘
                        │
                    ┌───┴───┐
                    │  马克  │
                    │ 面包店 │
                    └───────┘

图例:
── 友好关系 (friendship)
─── 竞争关系 (rivalry)
-.- 潜在冲突 (potential conflict)
```

---

## 9. 技术实现

### 9.1 技术栈

| 组件 | 技术选型 | 说明 |
|------|----------|------|
| **后端框架** | FastAPI | 异步、高性能 |
| **Agent 运行时** | Python + asyncio | 每个 Agent 独立协程 |
| **消息总线** | NATS | 轻量、支持多语言 |
| **数据库** | SQLite (Demo) / PostgreSQL | 状态持久化 |
| **LLM** | MiniMax (Coding Plan) | V3.5-Turbo 优先 |
| **前端** | React + Vite | 实时更新 |
| **WebSocket** | FastAPI 内置 | 推送更新 |

### 9.2 Agent 实例管理

```python
class AgentManager:
    def __init__(self):
        self.agents: Dict[str, Agent] = {}
        self.possessed: Optional[str] = None

    async def create_agent(self, config: CharacterConfig) -> Agent:
        agent = Agent(
            id=config.id,
            personality=PersonalityEngine(config),
            desire=DesireEngine(config.desire_thresholds),
            memory=MemorySystem(config.memory_config),
            emergence=EmergenceController(config.emergence_config),
            llm_client=LLMClient()  # 独立 API 调用
        )
        self.agents[config.id] = agent
        return agent

    async def tick_all(self, world_state: WorldState):
        tasks = []
        for agent_id, agent in self.agents.items():
            if agent_id != self.possessed:
                task = agent.think(world_state)
                tasks.append(task)

        results = await asyncio.gather(*tasks)
        return results

    def possess(self, agent_id: str, user_input: str):
        self.possessed = agent_id
        agent = self.agents[agent_id]
        return agent.process_user_input(user_input)

    def release_possession(self):
        self.possessed = None
```

### 9.3 MiniMax 集成

```python
class MiniMaxClient:
    def __init__(self, api_key: str, base_url: str = "https://api.minimax.chat/v1"):
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    async def chat(self, messages: List[Dict], model: str = "MiniMax-Text-01") -> str:
        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.7
        )
        return response.choices[0].message.content
```

---

## 10. 数据模型

### 10.1 Agent State

```python
class AgentState(BaseModel):
    id: str
    name: str
    location: str

    desire_state: DesireState
    personality_config: PersonalityConfig
    emergence_config: EmergenceConfig

    short_term_memory: List[MemoryItem] = []
    long_term_memory: List[MemoryItem] = []

    relationships: Dict[str, Relationship] = {}

    possession_mode: bool = False
    last_active_tick: int = 0
```

### 10.2 Social Event

```python
class SocialEvent(BaseModel):
    id: str
    tick: int
    type: EventType = Field(..., description="dialogue|action|conflict|cooperation")
    participants: List[str]
    content: str

    dialogue_turns: List[DialogueTurn] = []

    world_state_changes: Dict[str, Any] = {}

    outcome: EventOutcome
```

### 10.3 World State

```python
class WorldState(BaseModel):
    world_id: str
    tick: int
    game_date: str

    locations: List[Location]
    characters: List[str]

    relationships: Dict[str, Relationship]
    active_events: List[SocialEvent]

    world_rules: WorldRules
```

---

## 11. 开发阶段

### Phase 0: 核心验证 (2-3 周)

**目标**: 验证单个 Agent 的行为一致性

| 任务 | 说明 |
|------|------|
| Zyantine Core | 欲望引擎 + 人格配置 |
| Agent 单体 | 独立思考 + 状态更新 |
| MiniMax 集成 | API 调用 + Prompt 模板 |
| 简单对话 | 用户测试 Agent |

**验收标准**: 同一个问题问 5 次，Agent 的回答风格一致（差异 < 15%）

### Phase 1: 多 Agent 社交 (3-4 周)

**目标**: 3 个 Agent 可以互相交流

| 任务 | 说明 |
|------|------|
| Agent Mesh | NATS 消息传递 |
| WorldX 基础 | 空间 + 关系图谱 |
| 意图解析 | 冲突检测 + 对话生成 |
| 关系演化 | 互动影响关系 |

**验收标准**: 艾琳和马克可以自然对话超过 10 轮

### Phase 2: 时间系统 + 用户交互 (2-3 周)

**目标**: Tick 循环 + 附身模式

| 任务 | 说明 |
|------|------|
| Tick 调度 | 自动推进时间 |
| 旁观界面 | 实时观察 AI 社会 |
| 附身系统 | 用户接管 Agent |
| 中途添加 | 用户可添加角色/事件 |

**验收标准**: 用户可以在旁观模式和附身模式间切换

### Phase 3: 世界生成 + 完善 (3-4 周)

**目标**: AI 辅助生成完整世界

| 任务 | 说明 |
|------|------|
| 世界生成器 | AI 创建地点 + 角色 |
| 记忆系统 | 长期记忆 + 遗忘 |
| 涌现调优 | 不同角色的行为差异 |
| 性能优化 | 10+ Agent 并发 |

**验收标准**: 5 个 Agent 在生成的世界中自主运行 1 周（游戏时间）

---

## 12. 风险与对策

| 风险 | 影响 | 概率 | 对策 |
|------|------|------|------|
| Agent 人格渗透 | 高 | 高 | 严格隔离的上下文 + 定期人格一致性检测 |
| 循环对话 | 中 | 中 | 对话轮数限制 + 多样性激励 |
| 涌现失控 | 高 | 低 | 涌现参数硬上限 + ABSOLUTE 本能约束 |
| LLM 成本 | 中 | 中 | 限流 + 批量处理 + 缓存 |
| 社交关系崩溃 | 中 | 低 | 关系衰减有下限 + 冲突自动调解 |

---

## 13. 附录

### A. Agent 配置示例

```yaml
characters:
  - id: "elena"
    name: "艾琳"
    description: "翡翠城图书馆的管理员，谨慎而博学"
    age: 45
    personality:
      openness: 0.7      # 对新事物开放
      conscientiousness: 0.9  # 尽职尽责
      extraversion: 0.3   # 内向
      agreeableness: 0.8  # 和善
      neuroticism: 0.4    # 略神经质
    emergence:
      level: 0.4
      creativity_bias: 0.3
      randomness_factor: 0.2
      social_sensitivity: 0.7
      stubbornness: 0.6
    initial_location: "library"
    backstory: "在这里工作20年，把图书馆当成自己的家"

  - id: "max"
    name: "马克"
    description: "面包店老板，热情好客，喜欢聊天"
    age: 35
    personality:
      openness: 0.6
      conscientiousness: 0.7
      extraversion: 0.9   # 极度外向
      agreeableness: 0.8
      neuroticism: 0.2    # 情绪稳定
    emergence:
      level: 0.6
      creativity_bias: 0.5
      randomness_factor: 0.3
      social_sensitivity: 0.4
      stubbornness: 0.2   # 不固执
    initial_location: "bakery"
    backstory: "从父亲那里继承了面包店，手艺很好"
```

### B. 时间换算表

| 现实时间 | 游戏时间 |
|----------|----------|
| 1 分钟 | 1 小时 |
| 10 分钟 | 10 小时 |
| 1 小时 | 1 天 |
| 6 小时 | 6 天 |
| 24 小时 | 24 天 (约1个月) |

### C. 关系类型

| 类型 | 强度范围 | 演化方向 |
|------|----------|----------|
| stranger | 0.0-0.2 | → acquaintance |
| acquaintance | 0.2-0.4 | → friend / rival |
| friend | 0.4-0.7 | → close_friend / stranger |
| close_friend | 0.7-1.0 | → friend |
| rival | 0.0-0.4 | → enemy / acquaintance |
| enemy | -0.5-0.0 | → rival |
| romantic_interest | 0.5-0.8 | → lover / friend |
| lover | 0.8-1.0 | → close_friend |

---

**文档版本**: 2.1
**状态**: 待评审

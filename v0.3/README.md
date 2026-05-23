# World Pulse V0.3

AI 角色社交模拟平台 - 世界脉搏版本

## 功能特性

- 🌏 **AI 世界生成器**：根据简短描述自动生成完整世界
- 👥 **多角色社交模拟**：支持 3-5 个 AI 角色自主对话和互动
- 🕐 **时间与空间系统**：角色可在不同地点移动、相遇、触发对话
- 📖 **叙事引擎**：自动生成世界事件，丰富故事体验
- 🎭 **用户附身模式**：可附身到任意角色，通过输入控制角色行为
- 👁️ **实时旁观模式**：通过 Web 界面实时观察世界运行状态
- 💾 **世界持久化**：支持保存和加载世界状态

## 系统要求

- Python 3.11+
- Node.js 18+ (前端开发)
- Docker & Docker Compose (生产部署)

## 快速开始

### 本地开发

1. 创建虚拟环境并安装后端依赖：

```bash
cd server
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或: venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

2. 设置环境变量：

```bash
export MINIMAX_API_KEY="your-api-key-here"
```

3. 启动后端服务器：

```bash
python -m uvicorn server.api.server:app --reload --port 8000
```

4. 安装前端依赖并启动（可选）：

```bash
cd client
npm install
npm run dev
```

5. 打开浏览器访问 http://localhost:8000

### Docker 部署

```bash
export MINIMAX_API_KEY="your-api-key-here"
docker-compose up --build
```

## 项目结构

```
v0.3/
├── server/
│   ├── api/
│   │   └── server.py          # FastAPI 主服务器
│   ├── core/
│   │   ├── world_engine.py    # 世界引擎核心
│   │   ├── dialogue_engine.py  # 对话引擎
│   │   ├── agent.py           # Agent 实现
│   │   └── world_generator.py # AI 世界生成器
│   ├── plugins/
│   │   ├── interfaces.py      # 插件接口定义
│   │   └── default_plugins.py # 默认插件实现
│   └── utils/
│       └── llm_client.py      # LLM 客户端
├── client/
│   └── src/
│       └── App.tsx            # React 主组件
├── data/
│   ├── worlds/               # 世界模板存储
│   └── saves/               # 存档目录
├── docker-compose.yml
├── Dockerfile
└── README.md
```

## API 文档

服务器启动后访问：http://localhost:8000/docs

### 主要接口

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/world/state` | 获取当前世界状态 |
| POST | `/world/generate` | AI 生成新世界 |
| POST | `/agent/move` | 移动角色到指定位置 |
| POST | `/agent/possess` | 附身指定角色 |
| POST | `/agent/release` | 释放附身 |
| WS | `/ws` | WebSocket 实时通信 |

## 架构设计

### 插件化接口

遵循 SPEC 5.4-5.7 规范，实现以下接口：

- `IDesireEngine`: 欲望引擎，管理角色需求
- `IMemorySystem`: 记忆系统，短期+长期记忆
- `ILLMClient`: LLM 客户端，统一接口
- `IEventBus`: 事件总线，发布订阅模式
- `ISpaceSystem`: 空间系统，位置和移动管理
- `INarrativeEngine`: 叙事引擎，生成世界事件
- `IDialogueManager`: 对话管理器，协调多角色对话
- `IScheduler`: 调度器，分级 Tick 管理

### 分级调度

- **SILENT Tick**: 静默，不调用 LLM
- **NORMAL Tick**: 普通，标准 LLM 调用
- **CRITICAL Tick**: 关键，高频 LLM 调用

## 配置说明

环境变量：

| 变量名 | 描述 | 默认值 |
|--------|------|--------|
| `MINIMAX_API_KEY` | MiniMax API 密钥 | 必填 |
| `OLLAMA_HOST` | Ollama 服务地址 | http://localhost:11434 |

## 验收标准

- ✅ 3 个角色在 5 游戏天内自然移动、相遇、对话，无崩溃
- ✅ 能观察到一个环境驱动事件（如"暴风雨夜晚，角色关窗自语"）
- ✅ 运行 2 现实小时 API 费用受控于预算线

## 许可证

MIT License

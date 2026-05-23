# 项目启动文档：Athenaeum - 整合式拟人化AI角色平台

## 1. 项目概述

### 1.1 项目名称
**Athenaeum**（暂定名，亦可称为“智慧殿堂”或“Omnid”）

### 1.2 项目愿景
创建一个**能自我演化、拥有内在驱动力和丰富表达方式的“活体”数字生命**，使其能融入动态生成的虚拟世界，与用户建立真正有意义的连接。

### 1.3 核心价值
整合三个开源项目（WorldX、Zyantine、SillyTavern），弥补各自短板，形成一个“一句话创造有灵魂的AI角色并生活在动态世界中”的完整平台。

## 2. 三大核心组件定位

| 项目 | 核心定位 | 在整合中的角色 | 比喻 |
| :--- | :--- | :--- | :--- |
| **WorldX** | 世界生成器 + 模拟运行时 | 舞台与骨骼 | 身体（空间、时间、社会规则） |
| **Zyantine** | 内在人格架构 | 灵魂与驱动力 | 大脑与心脏（欲望驱动、本能） |
| **SillyTavern** | 角色扮演交互前端 | 脸与声音 | 口舌与表情（对话UI、多模态表现） |

## 3. 技术互补性分析

### 3.1 WorldX ↔ Zyantine
- WorldX提供外部环境刺激 & 多角色社会关系
- Zyantine提供内在欲望驱动 & 个性化成长
- **整合效果**：角色既为环境变化反应，也为自己欲望行动

### 3.2 WorldX ↔ SillyTavern
- WorldX提供地图、事件、角色调度
- SillyTavern提供对话界面、TTS、插件
- **整合效果**：用户可俯瞰世界，也可深度单聊

### 3.3 Zyantine ↔ SillyTavern
- Zyantine生成内在状态与决策
- SillyTavern将内在状态转化为丰富表达
- **整合效果**：AI说话不再靠硬编码，而源于真实的“欲望”

## 4. 阶段性目标

| 阶段 | 时间 | 目标 |
| :--- | :--- | :--- |
| **基础构建** | 0-3个月 | 打通基本流程，三套引擎并行，实现“输入→生成→聊天”闭环 |
| **功能孵化** | 3-9个月 | 深度整合：欲望驱动决策，辩证成长塑造人格，完成一个完整任务 |
| **生态扩展** | 9-18个月 | 多角色共存，复杂社交关系，形成小型“有灵魂的AI社会” |
| **成熟与创新** | 18个月+ | 社区生态，允许自定义逻辑，人机协作叙事生成 |

## 5. 风险评估与对策

| 风险 | 描述 | 对策 |
| :--- | :--- | :--- |
| **系统复杂度** | 三个项目依赖不同，调试困难 | 采用事件驱动架构 + 消息总线解耦；按功能划分微服务 |
| **项目成熟度** | Zyantine和WorldX较新，接口变动可能 | 设计抽象层隔离API变化；持续跟踪上游 |
| **性能与成本** | Token消耗大（生成一个WorldX世界需3~18万token） | 优先部署轻量本地模型（Llama 3 8B / Qwen 2.5 7B） |
| **安全与涌现** | 多智能体通信可能被伪造，闭环行为不可控 | 消息总线带身份校验；关键决策加入人工审批 |
| **测试复杂性** | LLM非确定性难以传统测试 | 建立LLM-Eval评测集，评估协同效能与一致性 |
| **系统健壮性** | 单点崩溃导致整体瘫痪 | 进程隔离；消息队列异步解耦；重试机制 |

## 6. 技术架构设计

### 6.1 整体架构图（文字描述）
- **表现层**：SillyTavern前端（React） + WorldX前端（React + Phaser 3）
- **网关层**：Go开发统一API Gateway，处理认证、路由、限流
- **业务逻辑层**：WorldX模拟引擎（Python）、Zyantine人格核心（Python）、SillyTavern后端（Node.js）
- **消息总线**：NATS / RabbitMQ，解耦各服务
- **数据层**：PostgreSQL（持久化） + Redis（缓存/状态）
- **AI模型层**：Ollama运行本地LLM（Llama 3, Qwen），可选OpenAI API

### 6.2 核心数据流
1. 用户通过前端发送“创造世界”请求 → API Gateway
2. Gateway调用WorldX服务生成世界蓝图，存入数据库
3. WorldX完成后触发事件，Zyantine为每个角色执行“人格建构”
4. 用户点击角色 → 拉起SillyTavern对话界面
5. 对话请求→Gateway→SillyTavern后端→Zyantine决策→返回回复
6. 世界Tick事件 → 消息总线 → 各角色Agent自主决策 → 更新状态

### 6.3 接口设计原则
- 所有服务间通信使用gRPC或REST + JSON，Protocol Buffers定义接口
- 每个服务提供健康检查和 metrics 端点
- 使用消息队列进行异步任务（如长时间生成）

## 7. 开发环境配置

### 7.1 硬件要求
- **CPU**：8核（建议i7/Ryzen 7）
- **内存**：32GB（多容器+本地模型的最低舒适区）
- **存储**：512GB NVMe SSD
- **网络**：稳定宽带 + 代理下载Docker镜像
- **可选GPU**：NVIDIA 8GB显存（用于本地LLM加速）

### 7.2 软件依赖

| 组件 | 技术要求 |
| :--- | :--- |
| **WorldX** | Python 3.10+（假设），需pygame等游戏库 |
| **Zyantine** | Python 3.10+，依赖openai SDK或本地模型调用 |
| **SillyTavern** | Node.js 18/20 LTS，npm |
| **网关** | Go 1.19+ |
| **消息总线** | NATS（推荐）或RabbitMQ |
| **数据库** | PostgreSQL 15+, Redis 7+ |
| **编排** | Docker + Docker Compose |
| **AI运行时** | Ollama |

### 7.3 推荐Docker Compose框架（见附录）

## 8. 开发工具与AI助手推荐

### 8.1 智能编程Agent
| 工具 | 适用场景 | 费用模式 |
| :--- | :--- | :--- |
| **Cursor** | 全项目快速开发、多服务联调 | $20/月 |
| **Claude Code** | 调试复杂逻辑、代码审查 | 按量计费 |
| **GitHub Copilot** | 日常代码补全、微调 | $10/月 或 $100/年 |
| **Cline** | 开源替代，需自带API Key | 免费（无API成本） |

### 8.2 推荐大模型
| 模型 | 优势 | 适用任务 |
| :--- | :--- | :--- |
| **Gemini 3.1 Pro** | 综合推理强 | 复杂系统设计 |
| **DeepSeek V4** | 1M上下文，免费 | 处理大型代码库 |
| **Qwen2.5-Coder** | 国产，92种语言 | 本地化部署偏好 |
| **Claude Sonnet** | 准确率高，Agentic能力强 | 逻辑深度任务 |

## 9. 集成策略（路线图）

### 第一步：节点打通（1-2周）
- 搭建Docker环境，分别运行三个项目
- 实现最简单的“用户 → 网关 → SillyTavern对话”流程

### 第二步：深度融合（3-4周）
- 编写网关与三者的REST/gRPC接口
- 实现数据闭环：WorldX生成角色 → Zyantine初始化 → 存入数据库

### 第三步：系统治理（2周）
- 增加用户认证、会话管理、日志监控
- 部署消息总线，解耦同步调用

### 第四步：AI模型接入（1周）
- 本地Ollama部署Llama 3 8B / Qwen 2.5 7B
- 配置SillyTavern连接本地模型

## 10. 附录：示例docker-compose.yaml

```yaml
version: '3.8'
services:
  nats-server:
    image: nats:latest
    ports:
      - "4222:4222"
  postgres-db:
    image: postgres:15
    environment:
      POSTGRES_PASSWORD: changeme
    volumes:
      - pgdata:/var/lib/postgresql/data
  redis-cache:
    image: redis:7-alpine
  sillytavern:
    image: sillytavern/sillytavern:latest
    ports:
      - "8000:8000"
    depends_on:
      - nats-server
  worldx:
    build: ./worldx  # 假设你有Dockerfile
    environment:
      - REDIS_URL=redis://redis-cache:6379
      - DB_URL=postgresql://postgres:changeme@postgres-db/worldx
    depends_on:
      - postgres-db
      - redis-cache
  zyantine:
    build: ./zyantine
    environment:
      - REDIS_URL=redis://redis-cache:6379
    depends_on:
      - redis-cache
  gateway:
    build: ./gateway
    ports:
      - "8080:8080"
    environment:
      - NATS_URL=nats://nats-server:4222
    depends_on:
      - nats-server
volumes:
  pgdata:
```

---

**文档版本**：1.0  
**创建日期**：2026-05-08  
**负责人**：项目发起人  
**审核状态**：待评审
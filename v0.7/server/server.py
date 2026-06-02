"""
server.py — V0.7 灵魂增强版 API 服务器
基于 V0.5 架构，集成 V0.7 灵魂系统
"""

import asyncio
import logging
import os
import sys
import threading
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect, Depends, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

current_dir = Path(__file__).parent
project_root = current_dir.parent.parent

sys.path.insert(0, str(current_dir))
sys.path.insert(1, str(project_root / "v0.5" / "server"))

from core.world_engine import WorldEngine, WorldConfig, Location, TimeOfDay, Weather, TickType
from core.dialogue_engine import DialogueManager
from core.agent import V05Agent
from core.v07_agent import V07Agent
from utils.llm_client import LLMClient
from utils.ollama_client import OllamaLLMClient
from core.memory_archiver import MemoryArchiver
from core.memory_retriever import MemoryRetriever
from core.forgetting_curve import ForgettingCurve
from core.model_router import create_default_router
from utils.llm_parsing import inject_guard, parse_llm_json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class AppState:
    """
    V0.7 服务器的进程级状态容器。
    取代过去的 module-level globals；通过 `app.state.app` 暴露给 FastAPI 依赖，
    通过 `get_state()` 给同步 helper 函数和 task 使用。
    """
    world: Optional[WorldEngine] = None
    llm: Optional[LLMClient] = None
    local_llm: Optional[OllamaLLMClient] = None
    dialogue_mgr: Optional[DialogueManager] = None
    memory_archiver: Optional[MemoryArchiver] = None
    memory_retriever: Optional[MemoryRetriever] = None
    model_router: object = None  # ModelRouter 实例（用于成本统计）
    agent_forgetting_curves: dict[str, ForgettingCurve] = field(default_factory=dict)
    llm_budget: object = None  # LLMBudget 实例（per-tick 限流）

    engine_running: bool = False
    tick_task: Optional[asyncio.Task] = None

    ws_clients: list = field(default_factory=list)  # 已连接的 WebSocket 客户端


# 模块级单例；`lifespan` 负责初始化，`get_state()` 给路由/task/WS handler 使用
state: Optional[AppState] = None


def get_state() -> AppState:
    """获取当前进程状态；服务器未启动时抛 503。"""
    if state is None:
        raise HTTPException(status_code=503, detail="服务器未初始化")
    return state


async def _broadcast_ws(payload: dict) -> None:
    """广播给所有已连接 WS 客户端；失败的客户端自动剔除。"""
    s = get_state()
    dead = []
    for client in list(s.ws_clients):
        try:
            await client.send_json(payload)
        except Exception:
            dead.append(client)
    for client in dead:
        try:
            s.ws_clients.remove(client)
        except ValueError:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    global state

    logger.info("V0.7 灵魂增强版服务器启动中...")

    ollama_base = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    use_ollama = os.environ.get("USE_OLLAMA", "1") == "1"

    cloud_llm = LLMClient(
        api_key=os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("MINIMAX_API_KEY"),
        base_url="https://api.minimaxi.com/anthropic",
        fallback_llm=None
    )

    local_llm = None
    if use_ollama:
        try:
            local_llm = OllamaLLMClient(base_url=ollama_base)
            logger.info("本地 Ollama 已连接")
        except Exception as e:
            logger.warning(f"Ollama 连接失败: {e}")
            local_llm = None

    # 注入 ModelRouter，使 LLM 客户端能记录调用成本
    # router 默认会注册到 PluginRegistry.get_router("default")
    model_router = create_default_router()
    cloud_llm.set_router(model_router)
    if local_llm is not None:
        local_llm.set_router(model_router)

    # V0.7: per-tick LLM 预算门(防止本地模型过载)
    from core.llm_budget import LLMBudget
    llm_budget = LLMBudget(
        max_concurrent=int(os.environ.get("ATHENAEUM_LLM_MAX_CONCURRENT", "2")),
        max_per_tick=int(os.environ.get("ATHENAEUM_LLM_MAX_PER_TICK", "4")),
    )
    if local_llm is not None:
        local_llm.set_budget(llm_budget)

    # V0.7: tick 间隔可配置
    tick_interval = float(os.environ.get("ATHENAEUM_TICK_INTERVAL", "30"))
    config = WorldConfig(tick_interval_seconds=tick_interval, save_interval_ticks=100)
    world = WorldEngine(config)

    # 设置 WS 广播函数：每次 tick 把状态推给所有已连接客户端
    world._ws_broadcast_fn = _broadcast_ws

    dialogue_mgr = DialogueManager(
        llm=local_llm or cloud_llm,
        world=world,
        archiver=None,
        retriever=None,
    )
    world.set_dialogue_manager(dialogue_mgr)

    memory_archiver = MemoryArchiver(
        cloud_llm=cloud_llm,
        local_llm=local_llm,
        chroma_client=None,
        forgetting_curves={},
    )

    memory_retriever = MemoryRetriever(
        local_llm=local_llm or cloud_llm,
        embedder=None,
        chroma_client=None,
    )

    state = AppState(
        world=world,
        llm=cloud_llm,
        local_llm=local_llm,
        dialogue_mgr=dialogue_mgr,
        memory_archiver=memory_archiver,
        memory_retriever=memory_retriever,
        model_router=model_router,
        llm_budget=llm_budget,
    )
    app.state.app = state

    logger.info("V0.7 服务器初始化完成")
    yield

    logger.info("V0.7 服务器关闭")
    state = None


app = FastAPI(title="Athenaeum V0.7", lifespan=lifespan)

# CORS：开发模式下前端（:5173 Vite / :3000 Docker）和生产模式（:8000 同源）都能访问。
# 限制 origin 比 `*` 更安全；用 environment override 可以让部署时更宽。
_default_origins = [
    "http://localhost:8000",   # 生产模式（FastAPI 同源）
    "http://127.0.0.1:8000",
    "http://localhost:5173",   # Vite dev
    "http://127.0.0.1:5173",
    "http://localhost:3000",   # Docker frontend
    "http://127.0.0.1:3000",
]
_extra = os.environ.get("ATHENAEUM_CORS_ORIGINS", "").strip()
if _extra:
    _default_origins += [o.strip() for o in _extra.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_default_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===== API Key 鉴权 =====
# 通过环境变量 ATHENAEUM_API_KEY 启用；不设置则所有路由不鉴权（开发模式）。
# 启用后，X-API-Key 必须匹配，否则所有非健康检查路由返回 401。
# WebSocket 鉴权见下方 _ws_auth_query()（WS 协议无法用 header，传 query 参数）。
_API_KEY = os.environ.get("ATHENAEUM_API_KEY", "").strip()


async def require_api_key(x_api_key: str = Header(default="", alias="X-API-Key")) -> None:
    """
    FastAPI 依赖：检查 X-API-Key。
    如果 ATHENAEUM_API_KEY 未设置，跳过鉴权（向后兼容）。
    """
    if not _API_KEY:
        return  # 未启用鉴权
    if x_api_key != _API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key header")


def check_ws_auth(query_token: str = "") -> bool:
    """
    WebSocket 鉴权：浏览器 WS API 不支持自定义 header，所以从 query 传 key。
    """
    if not _API_KEY:
        return True
    return query_token == _API_KEY


# 挂载静态资源
dist_path = current_dir.parent / "client" / "dist"
if dist_path.exists():
    app.mount("/assets", StaticFiles(directory=str(dist_path / "assets")), name="assets")


class AgentCreateRequest(BaseModel):
    id: str
    name: str
    personality: dict
    occupation: str = ""
    soul: dict = None
    initial_location: str = "图书馆"


class WorldCreateRequest(BaseModel):
    name: str
    locations: list[str]
    tick_interval: float = 2.0


class WorldGenerateRequest(BaseModel):
    description: str
    num_characters: int = 3
    model: str = "auto"  # "local", "cloud", "auto"


class WorldApplyRequest(BaseModel):
    world: dict
    characters: list
    relationships: list = []


@ app.get("/")
async def root():
    # dist 在 v0.7/client/dist, server 在 v0.7/server
    dist_path = current_dir.parent / "client" / "dist"
    index_path = dist_path / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "Athenaeum V0.7 灵魂增强版", "status": "running"}


@ app.get("/health")
async def health():
    """
    健康检查：探测 LLM 可用性。
    返回 200 = 至少一个 LLM 可用；503 = 全部不可用。
    前端 App.tsx 据此显示"已连接"/"未连接"。
    """
    s = get_state()

    local_ok = False
    cloud_ok = False

    async def probe_local():
        nonlocal local_ok
        if s.local_llm is None:
            return
        try:
            local_ok = await asyncio.wait_for(s.local_llm.health_check(), timeout=3.0)
        except Exception as e:
            logger.debug(f"[health] local probe failed: {e}")
            local_ok = False

    async def probe_cloud():
        nonlocal cloud_ok
        if s.llm is None:
            return
        try:
            cloud_ok = await asyncio.wait_for(s.llm.health_check(), timeout=5.0)
        except Exception as e:
            logger.debug(f"[health] cloud probe failed: {e}")
            cloud_ok = False

    # 并发探测（不串行等待）
    await asyncio.gather(probe_local(), probe_cloud())

    any_ok = local_ok or cloud_ok
    body = {
        "status": "healthy" if any_ok else "degraded",
        "version": "0.7",
        "local_llm": "up" if local_ok else "down",
        "cloud_llm": "up" if cloud_ok else ("not_configured" if s.llm is None or not s.llm._api_key else "down"),
    }
    if not any_ok:
        return JSONResponse(status_code=503, content=body)
    return body


@ app.get("/router/stats")
async def get_router_stats():
    """获取模型路由统计（供仪表盘查询）"""
    s = get_state()
    if not s.model_router:
        return {
            "local_calls": 0,
            "cloud_calls": 0,
            "degrade_active": False,
            "budget_remaining": 1.0,
            "budget_ratio": 0.0,
            "daily_budget": 10.0,
            "total_cost": 0.0,
        }

    stats = s.model_router.get_stats()
    return {
        "local_calls": stats.local_calls,
        "cloud_calls": stats.cloud_calls,
        "degrade_active": stats.degrade_active,
        "budget_remaining": stats.budget_remaining,
        "budget_ratio": stats.budget_ratio,
        "daily_budget": stats.daily_budget,
        "total_cost": stats.total_cost,
    }


@ app.post("/world/create")
async def create_world(req: WorldCreateRequest, _auth: None = Depends(require_api_key)):
    s = get_state()

    for loc_name in req.locations:
        loc_id = loc_name.lower().replace(" ", "_")
        s.world.register_location(Location(id=loc_id, name=loc_name))

    logger.info(f"世界已创建: {req.name}, 地点: {req.locations}")
    return {"message": "世界创建成功", "world": req.name}


@ app.post("/agent/create")
async def create_agent(req: AgentCreateRequest, _auth: None = Depends(require_api_key)):
    s = get_state()

    agent_id = req.id
    personality = req.personality or {
        "openness": 0.6,
        "conscientiousness": 0.7,
        "extraversion": 0.5,
        "agreeableness": 0.6,
        "neuroticism": 0.3,
    }

    if agent_id not in s.agent_forgetting_curves:
        s.agent_forgetting_curves[agent_id] = ForgettingCurve(agent_id)

    agent = V07Agent(
        agent_id=agent_id,
        name=req.name,
        personality=personality,
        occupation=req.occupation,
        soul=req.soul or {},
        llm=s.local_llm or s.llm,
        world=s.world,
        initial_location=req.initial_location,
        cloud_llm=s.llm,
        local_llm=s.local_llm,
        archiver=s.memory_archiver,
        retriever=s.memory_retriever,
        forgetting_curve=s.agent_forgetting_curves[agent_id],
    )

    s.world.register_agent(agent_id, req.name, req.initial_location)
    s.world.register_v07_agent(agent_id, agent)  # V0.7: 关键修复 — 把 agent 对象放入 registry
    await agent.initialize()  # 同步等待目标生成完成（来自 soul）
    logger.info(f"角色已创建: {req.name} ({agent_id})")

    return {"message": "角色创建成功", "agent_id": agent_id, "name": req.name}


@ app.post("/world/start")
async def start_world(_auth: None = Depends(require_api_key)):
    s = get_state()
    if s.engine_running:
        return {"message": "世界已在运行中"}

    s.engine_running = True
    s.tick_task = asyncio.create_task(_run_world_tick())

    # V0.7: 启动所有 agent 的决策循环
    started = 0
    reg_size = len(s.world._agent_registry) if s.world and s.world._agent_registry else 0
    logger.debug(f"[start] agent_registry size = {reg_size}")
    for agent in s.world._agent_registry.values():
        if hasattr(agent, 'start') and hasattr(agent, '_running') and not agent._running:
            try:
                agent.start()
                started += 1
            except Exception as e:
                logger.warning(f"启动 agent 失败: {e}")
    logger.info(f"已启动 {started} 个 agent 决策循环")

    return {"message": f"世界已启动,{started} 个 agent 进入决策循环"}


@ app.post("/world/stop")
async def stop_world(_auth: None = Depends(require_api_key)):
    s = get_state()
    s.engine_running = False
    if s.tick_task:
        s.tick_task.cancel()

    # V0.7: 优雅停止所有 agent 任务
    for agent in s.world._agent_registry.values():
        if hasattr(agent, 'stop'):
            try:
                await agent.stop()
            except Exception as e:
                logger.warning(f"停止 agent 失败: {e}")

    return {"message": "世界已停止"}


@ app.post("/world/generate_full")
async def generate_full_world(req: WorldGenerateRequest, _auth: None = Depends(require_api_key)):
    """
    生成完整世界：世界描述 + 角色 + 关系 + 性格提示
    使用 LLM 生成
    """
    s = get_state()

    # 选择模型：优先使用请求指定的模型，否则尝试本地再云端
    llm = None
    model_preference = getattr(req, 'model', None)
    if model_preference == 'local' and s.local_llm:
        llm = s.local_llm
    elif model_preference == 'cloud' and s.llm:
        # 云端需要检查是否真的可用（API Key 是否配置）
        if not s.llm._api_key:
            return {"error": "云端 MiniMax API 未配置 API Key。请设置 MINIMAX_API_KEY 或 ANTHROPIC_API_KEY 环境变量。"}
        llm = s.llm
    elif model_preference == 'cloud':
        return {"error": "云端 MiniMax API 未配置。请检查 API Key 环境变量。"}
    else:
        llm = s.local_llm or s.llm

    if not llm:
        return {"error": "无可用的 LLM 模型。请确保 Ollama 本地模型或云端 API 已配置。"}

    # 清洗用户输入：截断 + 转义 markdown 围栏，防止 prompt 注入
    if len(req.description) > 2000:
        return {"error": "世界描述过长（>2000 字符）"}
    safe_description = inject_guard(req.description, purpose="world_description")

    prompt = f"""你是一个世界构建专家。根据以下描述，生成一个详细的世界设定和角色。

世界描述：{safe_description}

请生成：
1. 世界名称、描述、氛围、地点、时间规则
2. {req.num_characters} 个角色，每个角色包含：
   - id, name, age, gender, pronouns
   - personality (Big Five 五因素，每个 0.0-1.0)
   - identity_tags (primary, secondary, self_identity)
   - backstory (title, childhood, adolescence, adulthood, present)
   - initial_location
   - introduce_text (角色自我介绍)
   - needs (初始需求)
3. 角色间的关系（from_id, to_id, relationship_type, strength, shared_history, potential_conflicts）
4. 性格互动提示（personality_tips：哪些角色互补/冲突/中性）

以 JSON 格式返回，包含：
- world: {{name, description, locations: [{{id, name, description, tags, capacity}}], time_rules: {{day_start_hour, day_end_hour, tick_interval_minutes}}, atmosphere: {{mood, dominant_themes, ambient_sounds}}}}
- characters: [{{id, name, age, gender, pronouns, personality: {{openness, conscientiousness, extraversion, agreeableness, neuroticism}}, identity_tags: {{primary, secondary, self_identity}}, backstory: {{title, childhood, adolescence, adulthood, present}}, initial_location, introduce_text, needs: [{{name, level}}]}}]
- relationships: [{{from_id, to_id, relationship_type, strength, shared_history, potential_conflicts}}]
- personality_tips: [{{from, to, type: "互补"|"冲突"|"中性", reason}}]

只返回 JSON，不要其他内容。"""

    try:
        response = await llm.chat(
            messages=[{"role": "user", "content": prompt}],
            system="你是一个世界构建专家，生成详细、有趣的虚构世界和角色。",
            temperature=0.8,
            max_tokens=4000,
        )

        content = response if isinstance(response, str) else response.content
        data = parse_llm_json(content)
        if data is not None:
            return data
        return {"error": "生成失败，JSON 解析错误", "raw": content[:500]}
    except Exception as e:
        logger.error(f"世界生成失败: {e}")
        return {"error": str(e)}


@ app.post("/world/apply")
async def apply_world(req: WorldApplyRequest, _auth: None = Depends(require_api_key)):
    """
    V0.7: 将生成的世界和角色应用到引擎。
    使用 WorldEngine.reset_world 创建 V07Agent 实例并注册到 _agent_registry。
    """
    s = get_state()

    if not s.world:
        raise HTTPException(status_code=400, detail="世界未创建，请先调用 /world/create")

    try:
        # V0.7: 停止现有 agent tasks(如果有)
        for agent in s.world._agent_registry.values():
            if hasattr(agent, '_task') and agent._task and not agent._task.done():
                try:
                    await agent.stop()
                except Exception as e:
                    logger.warning(f"停止旧 agent 失败: {e}")

        # V0.7: 准备 heartbeat 配置(通过 env)
        from core.heartbeat_mode import HeartbeatConfig
        hb_min = int(os.environ.get("ATHENAEUM_HEARTBEAT_MIN_TICKS", "4"))
        hb_max = int(os.environ.get("ATHENAEUM_HEARTBEAT_MAX_TICKS", "8"))

        # V0.7: forgetting_curves 包含每个 agent 的曲线,以及一个心跳配置(临时存放在特殊 key)
        curves_with_hb = dict(s.agent_forgetting_curves)
        curves_with_hb["_heartbeat_min"] = hb_min
        curves_with_hb["_heartbeat_max"] = hb_max

        # 调 reset_world 创建真正的 V07Agent 实例
        await s.world.reset_world(
            world_data=req.world,
            characters=req.characters,
            llm=s.local_llm or s.llm,
            cloud_llm=s.llm,
            local_llm=s.local_llm,
            archiver=s.memory_archiver,
            retriever=s.memory_retriever,
            forgetting_curves=curves_with_hb,
        )

        # 同步 session_id 到 memory 子系统
        session_id = s.world._world_session_id
        if s.memory_archiver is not None and hasattr(s.memory_archiver, 'set_session_id'):
            s.memory_archiver.set_session_id(session_id)
        if s.memory_retriever is not None and hasattr(s.memory_retriever, 'set_session_id'):
            s.memory_retriever.set_session_id(session_id)

        # V0.7: 把 relationships 交给 dialogue_mgr(尽管当前 set_relationships 是 no-op,保持接口)
        if req.relationships and s.dialogue_mgr is not None:
            if hasattr(s.dialogue_mgr, '_relationships_raw'):
                s.dialogue_mgr._relationships_raw = req.relationships
            if hasattr(s.dialogue_mgr, 'set_relationships'):
                s.dialogue_mgr.set_relationships(req.relationships)

        # V0.7: 如果引擎已在跑,启动所有新 agent 的决策循环
        if s.engine_running:
            for agent in s.world._agent_registry.values():
                if hasattr(agent, 'start'):
                    try:
                        agent.start()
                    except Exception as e:
                        logger.warning(f"启动 agent {agent._name} 失败: {e}")

        logger.info(
            f"世界已应用: {req.world.get('name', 'unknown')}, "
            f"{len(req.characters)} 个角色 (session={session_id})"
        )
        return {
            "message": f"世界'{req.world.get('name', '')}'已成功应用,{len(req.characters)}个角色已创建",
            "session_id": session_id,
            "agent_count": len(req.characters),
        }
    except Exception as e:
        logger.error(f"应用世界失败: {e}")
        return {"error": str(e)}


@ app.post("/dialogue/start")
async def start_dialogue(agent_a: str, agent_b: str, _auth: None = Depends(require_api_key)):
    s = get_state()

    if not s.world:
        raise HTTPException(status_code=400, detail="世界未创建")

    await s.dialogue_mgr.trigger_dialogue(agent_a, agent_b, s.world._agent_registry)
    return {"message": f"对话已开始: {agent_a} <-> {agent_b}"}


@ app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """
    V0.7 实时状态推送：每个 tick 把世界状态广播给所有已连接客户端。
    客户端可发 `possess`/`release` 消息来控制附身模式。

    【鉴权】当 ATHENAEUM_API_KEY 设置时，客户端必须传 `?token=<key>` query 参数。
    浏览器 WS API 不支持自定义 header，所以走 query 字符串。
    """
    s = get_state()
    token = ws.query_params.get("token", "")
    if not check_ws_auth(token):
        await ws.close(code=1008, reason="Unauthorized")
        logger.warning("[WS] 拒绝未鉴权连接")
        return
    await ws.accept()
    s.ws_clients.append(ws)
    logger.info(f"[WS] 客户端连接 (当前 {len(s.ws_clients)} 个)")
    try:
        while True:
            data = await ws.receive_json()
            msg_type = data.get("type")
            if msg_type == "ping":
                await ws.send_json({"type": "pong"})
            elif msg_type == "possess":
                agent_id = data.get("agent_id")
                message = data.get("message", "")
                if s.dialogue_mgr:
                    for session in s.dialogue_mgr._sessions.values():
                        if agent_id in (session.agent_a, session.agent_b):
                            if hasattr(session, "possess"):
                                session.possess(agent_id, message)
                            break
            elif msg_type == "release":
                if s.dialogue_mgr:
                    for session in s.dialogue_mgr._sessions.values():
                        if hasattr(session, "release"):
                            session.release()
            elif msg_type == "possess_message":
                # V0.7: 用户附身,直接 1-turn LLM 调用
                agent_id = data.get("agent_id")
                message = data.get("message", "")
                agent = s.world._agent_registry.get(agent_id) if s.world else None
                if agent is not None and hasattr(agent, 'respond_to_possess'):
                    try:
                        reply = await agent.respond_to_possess(message)
                        await ws.send_json({
                            "type": "possess_reply",
                            "agent_id": agent_id,
                            "text": reply,
                        })
                    except Exception as e:
                        logger.warning(f"[WS] possess 失败: {e}")
                        await ws.send_json({
                            "type": "possess_reply",
                            "agent_id": agent_id,
                            "text": f"(附身失败: {e})",
                        })
    except WebSocketDisconnect:
        pass
    finally:
        try:
            s.ws_clients.remove(ws)
        except ValueError:
            pass
        logger.info(f"[WS] 客户端断开 (当前 {len(s.ws_clients)} 个)")


async def _run_world_tick():
    s = get_state()

    while s.engine_running:
        try:
            # V0.7: per-tick 预算重置
            if s.llm_budget is not None:
                tick_id = getattr(s.world, '_tick_id', 0)
                s.llm_budget.on_tick_start(tick_id)

            await s.world.tick()
            # tick 完成后广播当前状态给所有 WS 客户端
            if s.ws_clients and s.world is not None:
                try:
                    state_resp = await get_world_state()
                    await _broadcast_ws({"type": "state", "data": state_resp})
                except Exception as e:
                    logger.debug(f"[WS] 广播失败: {e}")
            await asyncio.sleep(s.world.config.tick_interval_seconds)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Tick 执行错误: {e}")


@ app.get("/world/state")
async def get_world_state():
    """获取世界状态(V0.7: 用 _serialize_agents 读富字段)"""
    s = get_state()

    if not s.world:
        return {"tick_id": 0, "time_of_day": "unknown", "weather": "unknown", "agents": [], "locations": [], "dialogues": []}

    # V0.7: 用引擎的 _serialize_agents 读 personality/emotion/goal 等富字段
    if hasattr(s.world, '_serialize_agents'):
        agents_data = s.world._serialize_agents()
    else:
        # 兜底:旧路径
        agents_data = []
        if hasattr(s.world, '_agents'):
            for agent_id, agent_data in s.world._agents.items():
                agents_data.append({
                    "id": agent_id,
                    "name": s.world.agent_names.get(agent_id, agent_id),
                    "location": "unknown",
                })

    recent_dialogues = []
    if s.dialogue_mgr and getattr(s.dialogue_mgr, '_sessions', None):
        for session in s.dialogue_mgr._sessions.values():
            recent_dialogues.extend(getattr(session, 'conversation_log', [])[-20:])
    recent_dialogues = recent_dialogues[-20:]

    return {
        "tick_id": getattr(s.world, '_tick_id', 0),
        "time": {
            "game_hour": getattr(s.world, '_game_hour', 8),
            "time_of_day": str(getattr(s.world, '_time_of_day', 'unknown')).replace('TimeOfDay.', '').lower(),
        },
        "weather": str(getattr(s.world, '_weather', 'unknown')).replace('Weather.', '').lower(),
        "tick_type": "normal",
        "agents": agents_data,
        "locations": s.world._serialize_locations() if hasattr(s.world, '_serialize_locations') else ([loc.name for loc in s.world.get_all_locations()] if hasattr(s.world, 'get_all_locations') else []),
        "dialogues": [
            {"from": d.from_agent, "to": d.to_agent, "utterance": d.utterance, "micro_action": getattr(d, 'micro_action', None), "tick": getattr(d, 'tick', 0)}
            for d in recent_dialogues
        ],
        "session_id": getattr(s.world, '_world_session_id', None),
    }


@ app.post("/server/stop")
async def stop_server(_auth: None = Depends(require_api_key)):
    """
    优雅关闭服务器：
    1. 停止世界 tick loop
    2. 取消所有进行中的对话 task
    3. sys.exit(0) — uvicorn 会关闭 socket 退出进程
    比 SIGTERM 安全：多 worker / 容器里不会杀错进程。
    """
    s = get_state()

    logger.info("收到关闭指令，正在停止服务器...")

    # 1. 停世界 tick
    s.engine_running = False
    if s.tick_task and not s.tick_task.done():
        s.tick_task.cancel()
        try:
            await s.tick_task
        except (asyncio.CancelledError, Exception):
            pass

    # 1.5 停所有 agent 决策循环
    for agent in s.world._agent_registry.values() if s.world else []:
        if hasattr(agent, 'stop'):
            try:
                await agent.stop()
            except Exception:
                pass

    # 2. 取消所有对话 task
    if s.dialogue_mgr is not None:
        for task in list(getattr(s.dialogue_mgr, '_session_tasks', set())):
            if not task.done():
                task.cancel()
        for task in list(getattr(s.world, '_dialogue_tasks', set()) if s.world else []):
            if not task.done():
                task.cancel()

    # 3. 退出进程（用 sys.exit 比 os.kill(SIGTERM) 更安全：
    #    多 worker 不会杀错、K8s/容器里信号不会丢、uvicorn 自身也能正常 drain）
    logger.info("服务器已停止")
    # 在 finally 之外退出；先返回 200 让客户端知道收到指令
    def _exit():
        sys.exit(0)
    threading.Timer(0.5, _exit).start()
    return {"message": "服务器已停止，进程将退出"}


@ app.post("/engine/pause")
async def engine_pause(_auth: None = Depends(require_api_key)):
    """暂停世界 tick + 所有 agent 决策循环"""
    s = get_state()
    s.engine_running = False
    if s.tick_task and not s.tick_task.done():
        s.tick_task.cancel()
        try:
            await s.tick_task
        except (asyncio.CancelledError, Exception):
            pass
    for agent in s.world._agent_registry.values() if s.world else []:
        if hasattr(agent, 'stop'):
            try:
                await agent.stop()
            except Exception:
                pass
    return {"message": "已暂停"}


@ app.post("/engine/resume")
async def engine_resume(_auth: None = Depends(require_api_key)):
    """恢复世界 tick + 所有 agent 决策循环"""
    s = get_state()
    if s.engine_running:
        return {"message": "已在运行中"}
    s.engine_running = True
    s.tick_task = asyncio.create_task(_run_world_tick())
    for agent in s.world._agent_registry.values():
        if hasattr(agent, 'start') and hasattr(agent, '_running') and not agent._running:
            try:
                agent.start()
            except Exception as e:
                logger.warning(f"恢复 agent 失败: {e}")
    return {"message": "已恢复"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
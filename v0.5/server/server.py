"""
server.py — V0.5 记忆回廊 API 服务器
在 V0.4 基础上新增记忆系统
"""

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

from pydantic import BaseModel

current_dir = Path(__file__).parent
server_dir = current_dir  # V0.5 server 目录
project_root = current_dir.parent.parent  # /Volumes/Ollama-Models/Athenaeum

# 添加 V0.5 server 路径（优先）
sys.path.insert(0, str(server_dir))

# 添加 V0.4 路径（包含 world_models 和 worldsmith）
v04_path = project_root / "v0.4"
sys.path.insert(1, str(v04_path))

# 添加 V0.3 server 路径（包含 core 和 utils）
v03_server_path = project_root / "v0.3" / "server"
sys.path.insert(2, str(v03_server_path))

# 添加项目根路径
sys.path.insert(3, str(project_root))

from core.world_engine import WorldEngine, WorldConfig, Location
from core.dialogue_engine import DialogueManager
from core.agent import V05Agent, MinimalAgent
from utils.llm_client import LLMClient

# V0.5 记忆系统
from core.memory_archiver import MemoryArchiver
from core.memory_retriever import MemoryRetriever
from core.forgetting_curve import ForgettingCurve

# V0.6 叙事引擎
from core.collective_mood import CollectiveMood
from core.opportunity_detector import OpportunityDetector
from core.narrative_injector import NarrativeInjector
from core.world_will import WorldWill
from api.journal import TimelineService

# V0.4 Worldsmith
from worldsmith import Worldsmith
from world_models import WorldsmithGenerateRequest, CharacterBatchRequest, RelationshipGenerateRequest

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_world: WorldEngine = None
_llm: LLMClient = None
_local_llm = None
_dialogue_mgr: DialogueManager = None
_engine_running: bool = False
_tick_task: asyncio.Task = None
_engine_paused: bool = False

# V0.5 记忆系统组件
_memory_archiver: MemoryArchiver = None
_memory_retriever: MemoryRetriever = None
_agent_forgetting_curves: dict[str, ForgettingCurve] = {}
_embedder = None  # bge-m3 嵌入模型

# V0.6 叙事引擎组件
_collective_mood: CollectiveMood = None
_opportunity_detector: OpportunityDetector = None
_narrative_injector: NarrativeInjector = None
_world_will: WorldWill = None
_timeline_service: TimelineService = None

# V0.4 Worldsmith
_worldsmith: Worldsmith = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _world, _llm, _local_llm, _dialogue_mgr, _engine_running, _tick_task, _engine_paused
    global _memory_archiver, _memory_retriever, _agent_forgetting_curves
    global _collective_mood, _opportunity_detector, _narrative_injector, _world_will, _timeline_service
    global _worldsmith, _model_router

    use_ollama = os.environ.get("USE_OLLAMA", "").lower() in ("1", "true", "yes")

    _engine_running = False
    _engine_paused = False
    _tick_task = None

    if use_ollama:
        from utils.ollama_client import OllamaLLMClient
        _llm = OllamaLLMClient()
        _local_llm = _llm
        logger.info("[Server] 使用本地 Ollama (qwen3.5:4b)")
    else:
        try:
            from utils.ollama_client import OllamaLLMClient
            _local_llm = OllamaLLMClient()
            _llm = LLMClient(fallback_llm=_local_llm)
            logger.info("[Server] 使用云端 LLM (MiniMax)，fallback: 本地 Ollama")
            cloud_ok = await _llm.health_check()
            if cloud_ok:
                logger.info("[Server] 云端 LLM 正常")
            else:
                logger.info("[Server] 云端 LLM 不可用，将使用本地 Ollama")
        except Exception as e:
            _local_llm = None
            _llm = LLMClient()
            logger.info(f"[Server] 使用云端 LLM (MiniMax)，无 fallback: {e}")

    config = WorldConfig(tick_interval_seconds=2.0, save_interval_ticks=100)
    _world = WorldEngine(config)

    # V0.5: 初始化 Chroma 客户端（持久化到本地）
    chroma_path = current_dir / "chroma_data"
    chroma_path.mkdir(exist_ok=True)
    try:
        import chromadb
        _chroma_client = chromadb.PersistentClient(path=str(chroma_path))
        logger.info(f"[Server] Chroma 已初始化，路径: {chroma_path}")
    except Exception as e:
        logger.warning(f"[Server] Chroma 初始化失败: {e}，将使用内存存储")
        _chroma_client = None

    # V0.5: 初始化记忆系统组件
    from utils.ollama_client import OllamaLLMClient
    _embedder = OllamaLLMClient(model="bge-m3")
    _agent_forgetting_curves = {}  # 先定义
    _memory_archiver = MemoryArchiver(cloud_llm=_llm, local_llm=_local_llm, chroma_client=_chroma_client, forgetting_curves=_agent_forgetting_curves)
    _memory_retriever = MemoryRetriever(local_llm=_local_llm, chroma_client=_chroma_client, embedder=_embedder)

    # V0.7: 初始化模型路由器（必须在 DialogueManager 之前）
    from core.model_router import ModelRouter
    _model_router = ModelRouter(daily_budget=10.0)

    _dialogue_mgr = DialogueManager(_local_llm or _llm, _world, archiver=_memory_archiver, retriever=_memory_retriever, router=_model_router)
    _world.set_dialogue_manager(_dialogue_mgr)

    # V0.6: 初始化叙事引擎组件
    _collective_mood = CollectiveMood(_world)
    _opportunity_detector = OpportunityDetector(_world, _collective_mood)
    _world_will = WorldWill()
    _narrative_injector = NarrativeInjector(
        world=_world,
        cloud_llm=_llm,
        tension_threshold=0.3,
        window_ticks=10,
        world_will=_world_will,
    )
    _timeline_service = TimelineService(_world)

    # V0.6: 注册叙事引擎组件到 WorldEngine
    _world.set_collective_mood(_collective_mood)
    _world.set_opportunity_detector(_opportunity_detector)
    _world.set_narrative_injector(_narrative_injector)
    _world.set_world_will(_world_will)
    _world.set_timeline_service(_timeline_service)
    _world.set_archiver(_memory_archiver)
    _world.set_ws_broadcast(lambda p: _broadcast_ws(p))

    # V0.4 Worldsmith
    _worldsmith = Worldsmith(_llm, _local_llm)
    logger.info("[Server] V0.4 世界工坊已就绪")

    logger.info("[Server] V0.6 命运纺机已就绪")
    yield
    logger.info("[Server] 关闭中...")


app = FastAPI(title="World Pulse API", version="0.5.0", lifespan=lifespan)

# 静态文件挂载（复用 V0.3 前端）
static_dir = project_root / "v0.3" / "client" / "dist"
app.mount("/assets", StaticFiles(directory=str(static_dir / "assets")), name="assets")
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# V0.4 世界工坊静态文件
worldsmith_static_dir = project_root / "v0.4" / "worldsmith_client" / "dist"
if worldsmith_static_dir.exists():
    app.mount("/worldsmith/assets", StaticFiles(directory=str(worldsmith_static_dir / "assets")), name="worldsmith_assets")


# =============================================================================
# V0.5 记忆系统路由
# =============================================================================

@app.get("/agent/{agent_id}/journal")
async def get_agent_journal(agent_id: str, page: int = 1, size: int = 10):
    """获取角色日记（长期记忆摘要）—— 双源读取：ForgettingCurve（内存）+ Chroma（持久化）"""
    global _agent_forgetting_curves, _memory_retriever

    current_tick = getattr(_world, '_tick_id', 0) if _world else 0

    # 1. 先读 ForgettingCurve（内存）
    memory_ids_seen = set()
    all_memories = []
    if agent_id in _agent_forgetting_curves:
        curve = _agent_forgetting_curves[agent_id]
        all_memories = curve.get_recent_memories(current_tick, max_count=100)
        memory_ids_seen = {m.memory_id for m in all_memories}

    # 2. 再从 Chroma 读取（跨服恢复）
    chroma_entries = []
    if _memory_retriever:
        try:
            chroma_entries = await _memory_retriever.retrieve_by_agent(agent_id, max_count=100)
        except Exception as e:
            logger.warning(f"[Journal] [{agent_id}] Chroma 读取失败: {e}")

    # 3. 合并：以 memory_id 为 key，内存优先
    merged_map = {m.memory_id: m for m in all_memories}
    restored_count = 0
    for entry in chroma_entries:
        if entry.memory_id not in merged_map:
            # Chroma 有、内存无 → 跨服恢复
            merged_map[entry.memory_id] = entry
            restored_count += 1
            # 写回 ForgettingCurve
            if agent_id in _agent_forgetting_curves:
                _agent_forgetting_curves[agent_id].add_memory(entry)

    if restored_count > 0:
        logger.info(f"[Journal] [{agent_id}] 从 Chroma 跨服恢复 {restored_count} 条记忆")

    # 重新获取合并后的列表（按 tick_created 倒序）
    all_memories = sorted(merged_map.values(), key=lambda m: m.tick_created, reverse=True)

    # 分页
    start = (page - 1) * size
    end = start + size
    page_memories = all_memories[start:end]

    return {
        "agent_id": agent_id,
        "memories": [
            {
                "memory_id": m.memory_id,
                "content": m.content,
                "emotion": m.emotion,
                "importance": m.importance,
                "tick_created": m.tick_created,
                "is_core": m.is_core,
                "context": m.context,
            }
            for m in page_memories
        ],
        "total": len(all_memories),
        "page": page,
        "size": size,
        "restored_from_chroma": restored_count,
    }


@app.get("/agent/{agent_id}/memory/stats")
async def get_memory_stats(agent_id: str):
    """获取角色记忆统计"""
    global _agent_forgetting_curves, _memory_archiver

    stats = {
        "agent_id": agent_id,
        "total_memories": 0,
        "core_memories": 0,
        "pending_archival": 0,
    }

    if agent_id in _agent_forgetting_curves:
        curve = _agent_forgetting_curves[agent_id]
        stats["total_memories"] = curve.size()
        stats["core_memories"] = sum(1 for m in curve.get_all_memories() if m.is_core)

    if _memory_archiver:
        stats["pending_archival"] = _memory_archiver.get_pending_count(agent_id)

    return stats


@app.post("/agent/{agent_id}/memory/force_archive")
async def force_archive(agent_id: str):
    """强制归档指定角色的待归档对话"""
    global _memory_archiver, _agent_forgetting_curves

    if not _memory_archiver:
        raise HTTPException(status_code=500, detail="记忆系统未初始化")

    current_tick = getattr(_world, '_tick_id', 0) if _world else 0

    # 直接调用 archiver
    summary = await _memory_archiver.archive_if_needed(agent_id, current_tick, force=True)

    if summary:
        # 添加到遗忘曲线
        if agent_id not in _agent_forgetting_curves:
            _agent_forgetting_curves[agent_id] = ForgettingCurve(agent_id, neuroticism=0.5)

        from core.forgetting_curve import MemoryEntry
        entry = MemoryEntry(
            memory_id=summary.memory_id,
            agent_id=agent_id,
            content=summary.summary_text,
            tick_created=current_tick,
            importance=summary.importance_score,
            emotion=summary.emotion,
            is_core=summary.core_memory,
            context=f"participants: {summary.participants}",
        )
        _agent_forgetting_curves[agent_id].add_memory(entry)

        return {"status": "ok", "memory_id": summary.memory_id, "summary": summary.summary_text}
    else:
        return {"status": "no_data", "message": "没有待归档的对话"}


@app.post("/agent/{agent_id}/memory/prune")
async def prune_memories(agent_id: str):
    """清理过期记忆"""
    global _agent_forgetting_curves

    if agent_id not in _agent_forgetting_curves:
        return {"status": "ok", "deleted": []}

    current_tick = getattr(_world, '_tick_id', 0) if _world else 0
    deleted = _agent_forgetting_curves[agent_id].prune_memories(current_tick)

    return {"status": "ok", "deleted": deleted}


# =============================================================================
# V0.6 叙事引擎路由
# =============================================================================

@app.get("/world/timeline")
async def get_timeline(page: int = 1, size: int = 20, event_type: str = None):
    """获取世界大事记时间线"""
    global _timeline_service

    if not _timeline_service:
        raise HTTPException(status_code=500, detail="TimelineService 未初始化")

    return _timeline_service.get_timeline(page, size, event_type)


@app.get("/world/mood")
async def get_collective_mood():
    """获取当前集体情绪状态"""
    global _collective_mood

    if not _collective_mood:
        raise HTTPException(status_code=500, detail="CollectiveMood 未初始化")

    mood = _collective_mood.get_mood()
    trend = _collective_mood.get_trend()
    state = _collective_mood.get_state()

    return {
        "mood": mood,
        "trend": trend,
        "tension_relief": state.get("tension_relief", 0.0),
        "crisis_stability": state.get("crisis_stability", 0.0),
        "social_affection": state.get("social_affection", 0.0),
    }


@app.get("/world/opportunities")
async def get_opportunities():
    """获取当前检测到的世界机会"""
    global _opportunity_detector

    if not _opportunity_detector:
        raise HTTPException(status_code=500, detail="OpportunityDetector 未初始化")

    if not _world:
        return {"opportunities": []}

    agents = list(_world._agents.values())
    signals = _opportunity_detector.scan(agents)

    return {
        "opportunities": [
            {
                "type": sig.signal_type.value if hasattr(sig.signal_type, 'value') else str(sig.signal_type),
                "participants": sig.participants,
                "location": sig.location,
                "strength": sig.strength,
                "description": sig.description,
            }
            for sig in signals
        ]
    }


# =============================================================================
# V0.7 模型路由统计
# =============================================================================

@app.get("/router/stats")
async def get_router_stats():
    """获取模型路由统计（供仪表盘查询）"""
    global _model_router

    if not _model_router:
        # 返回默认值（未初始化时）
        return {
            "local_calls": 0,
            "cloud_calls": 0,
            "degrade_active": False,
            "budget_remaining": 1.0,
            "budget_ratio": 0.0,
            "daily_budget": 10.0,
            "total_cost": 0.0,
        }

    stats = _model_router.get_stats()
    return {
        "local_calls": stats.local_calls,
        "cloud_calls": stats.cloud_calls,
        "degrade_active": stats.degrade_active,
        "budget_remaining": stats.budget_remaining,
        "budget_ratio": stats.budget_ratio,
        "daily_budget": stats.daily_budget,
        "total_cost": stats.total_cost,
    }


# =============================================================================
# V0.4 世界工坊路由
# =============================================================================

class GenerateWorldRequest(BaseModel):
    description: str


class GenerateCharactersRequest(BaseModel):
    world_description: str
    locations: list[str]
    num_characters: int = 3


class GenerateRelationshipsRequest(BaseModel):
    characters: list[dict]


@app.get("/worldsmith")
async def worldsmith():
    ws_index_path = worldsmith_static_dir / "index.html"
    if ws_index_path.exists():
        from fastapi.responses import FileResponse
        return FileResponse(ws_index_path)
    return {"message": "Worldsmith V0.5", "status": "not found"}


# -------------------------------------------------------------------------
# 世界生成
# -------------------------------------------------------------------------

@app.post("/world/generate")
async def generate_world(req: GenerateWorldRequest):
    """生成世界骨架（云端 MiniMax + 本地 Qwen 校验）"""
    world = await _worldsmith.generate_world(req.description)
    return {
        "name": world.name,
        "description": world.description,
        "locations": [loc.model_dump() for loc in world.locations],
        "time_rules": world.time_rules.model_dump(),
        "atmosphere": world.atmosphere.model_dump(),
    }


@app.post("/world/generate_full")
async def generate_world_full(req: WorldsmithGenerateRequest):
    """完整世界工坊流程"""
    try:
        result = await _worldsmith.generate_full_world(req)
        return {
            "world": result["world"].model_dump(),
            "characters": [c.model_dump() for c in result["characters"]],
            "relationships": [r.model_dump() for r in result["relationships"]],
            "personality_tips": result["personality_tips"],
            "metrics": result["metrics"].model_dump(),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/world/apply")
async def apply_generated_world(req: dict):
    """将生成的世界和角色应用到世界引擎，并启动引擎"""
    global _engine_running, _tick_task

    world_data = req.get("world", {})
    characters = req.get("characters", [])
    relationships = req.get("relationships", [])

    await _world.reset_world(world_data, characters, _local_llm or _llm)

    # V0.7: 同步世界会话 ID 到归档器和检索器（实现数据隔离）
    _memory_archiver.set_session_id(_world._world_session_id)
    _memory_retriever.set_session_id(_world._world_session_id)

    # 将关系数据传递给对话管理器
    _dialogue_mgr.set_relationships(relationships)

    if not _engine_running:
        _tick_task = asyncio.create_task(_tick_loop())
        _engine_running = True
        logger.info("[Server] 世界引擎已启动")

    return {"status": "ok", "message": f"已加载 {len(world_data.get('locations', []))} 个地点, {len(characters)} 个角色, {len(relationships)} 条关系，引擎已启动"}


# -------------------------------------------------------------------------
# 角色生成
# -------------------------------------------------------------------------

@app.post("/characters/generate")
async def generate_characters(req: GenerateCharactersRequest):
    """批量生成角色配置（云端 + 本地 introduce_text）"""
    batch_req = CharacterBatchRequest(
        world_description=req.world_description,
        locations=req.locations,
        num_characters=req.num_characters,
    )
    characters = await _worldsmith.generate_characters(batch_req)
    return {
        "characters": [c.model_dump() for c in characters],
    }


# -------------------------------------------------------------------------
# 关系生成
# -------------------------------------------------------------------------

@app.post("/relationships/generate")
async def generate_relationships(req: GenerateRelationshipsRequest):
    """编织角色间关系（云端 shared_history + 本地视角校验）"""
    from world_models import CharacterConfig
    characters = [CharacterConfig(**c) for c in req.characters]
    relationships = await _worldsmith.generate_relationships(characters)
    return {
        "relationships": [r.model_dump() for r in relationships],
    }


@app.get("/worldsmith/metrics")
async def get_worldsmith_metrics():
    """获取 Token 消耗统计"""
    return _worldsmith.metrics.model_dump()


# =============================================================================
# V0.3 原有路由（保留）
# =============================================================================

@app.get("/")
async def root():
    index_path = static_dir / "index.html"
    if index_path.exists():
        from fastapi.responses import FileResponse
        return FileResponse(index_path)
    return {"message": "World Pulse V0.5 API", "version": "0.5.0"}


@app.get("/world/state")
async def get_world_state():
    return {
        "tick_id": _world._tick_id,
        "time": {"game_hour": _world._game_hour, "time_of_day": _world._time_of_day.value},
        "weather": _world._weather.value,
        "agents": _world._serialize_agents(),
        "locations": _world._serialize_locations(),
        "recent_dialogues": _world._recent_dialogues[-20:],
        "recent_actions": _world._recent_actions[-15:],
    }


async def _tick_loop():
    while True:
        try:
            if not _engine_paused:
                result = await _world.tick()
            else:
                # 暂停时发送心跳状态
                result = _world._get_state()
            await _broadcast_ws(result)
            await asyncio.sleep(_world.config.tick_interval_seconds)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"[Tick Loop] 错误: {e}")


async def _broadcast_ws(data: dict):
    global _ws_clients
    if not _ws_clients:
        return
    for client in _ws_clients[:]:
        try:
            await client.send_json(data)
        except Exception:
            _ws_clients.remove(client)


_ws_clients: list = []


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    _ws_clients.append(ws)
    try:
        while True:
            data = await ws.receive_json()
            if data.get("type") == "possess":
                agent_id = data.get("agent_id")
                message = data.get("message", "")
                for session in _dialogue_mgr._sessions.values():
                    if agent_id in (session.agent_a, session.agent_b):
                        session.possess(agent_id, message)
                        break
            elif data.get("type") == "release":
                for session in _dialogue_mgr._sessions.values():
                    session.release()
    except WebSocketDisconnect:
        _ws_clients.remove(ws)


@app.post("/world/reset")
async def reset_world(world_data: dict, characters: list[dict]):
    """重置世界（复用 V0.3 逻辑）"""
    global _engine_running, _tick_task, _agent_forgetting_curves

    from core.agent import MinimalAgent

    # 清空遗忘曲线
    _agent_forgetting_curves.clear()

    await _world.reset_world(world_data, characters, _local_llm or _llm)

    # V0.7: 同步世界会话 ID 到归档器和检索器（实现数据隔离）
    _memory_archiver.set_session_id(_world._world_session_id)
    _memory_retriever.set_session_id(_world._world_session_id)

    # 为每个角色创建遗忘曲线
    for char in characters:
        agent_id = char.get("id")
        neuroticism = char.get("personality", {}).get("neuroticism", 0.5)
        _agent_forgetting_curves[agent_id] = ForgettingCurve(agent_id, neuroticism)

    # 重新初始化 V05Agent
    for char in characters:
        agent_id = char.get("id")
        name = char.get("name", agent_id)
        personality = char.get("personality", {})
        location_id = char.get("initial_location", "")

        agent = MinimalAgent(
            agent_id=agent_id,
            name=name,
            world=_world,
            llm=_local_llm or _llm,
            initial_location=location_id,
        )
        agent.personality = personality

        _world.register_agent(agent_id, name, location_id)
        _world.register_v05_agent(agent_id, agent)

    if not _engine_running:
        _tick_task = asyncio.create_task(_tick_loop())
        _engine_running = True
        logger.info("[Server] 世界引擎已启动")

    return {"status": "ok"}


@app.post("/agent/move")
async def move_agent(agent_id: str, target_location: str):
    success = _world.move_agent(agent_id, target_location)
    if not success:
        raise HTTPException(status_code=400, detail="移动失败")
    return {"success": True}


@app.post("/agent/possess")
async def possess_agent(agent_id: str, message: str):
    for session_pair, session in _dialogue_mgr._sessions.items():
        if agent_id in session_pair:
            session.possess(agent_id, message)
            break
    return {"success": True, "possessed": agent_id}


@app.post("/agent/release")
async def release_possession():
    for session in _dialogue_mgr._sessions.values():
        session.release()
    return {"success": True}


@app.get("/dialogue/active")
async def get_active_dialogues():
    return {
        "active_agents": list(_dialogue_mgr._active_agents),
        "session_count": len(_dialogue_mgr._sessions),
    }


@app.post("/engine/pause")
async def pause_engine():
    """暂停世界引擎"""
    global _engine_paused, _dialogue_mgr
    _engine_paused = True
    # 停止所有对话会话
    if _dialogue_mgr:
        for session in list(_dialogue_mgr._sessions.values()):
            session.stop()
        _dialogue_mgr._sessions.clear()
        _dialogue_mgr._active_agents.clear()
    return {"success": True, "paused": True}


@app.post("/engine/resume")
async def resume_engine():
    """恢复世界引擎"""
    global _engine_paused
    _engine_paused = False
    return {"success": True, "paused": False}


@app.get("/engine/status")
async def get_engine_status():
    """获取引擎状态"""
    return {
        "running": _engine_running,
        "paused": _engine_paused,
        "tick_id": _world._tick_id if _world else 0,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
"""
server.py — V0.7 灵魂增强版 API 服务器
基于 V0.5 架构，集成 V0.7 灵魂系统
"""

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_world: WorldEngine = None
_llm: LLMClient = None
_local_llm = None
_dialogue_mgr: DialogueManager = None
_engine_running: bool = False
_tick_task: asyncio.Task = None

_memory_archiver: MemoryArchiver = None
_memory_retriever: MemoryRetriever = None
_agent_forgetting_curves: dict[str, ForgettingCurve] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _world, _llm, _local_llm, _dialogue_mgr
    global _memory_archiver, _memory_retriever, _agent_forgetting_curves

    logger.info("V0.7 灵魂增强版服务器启动中...")

    ollama_base = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    use_ollama = os.environ.get("USE_OLLAMA", "1") == "1"

    _llm = LLMClient(
        api_key=os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("MINIMAX_API_KEY"),
        base_url="https://api.minimaxi.com/anthropic",
        fallback_llm=None
    )

    if use_ollama:
        try:
            _local_llm = OllamaLLMClient(base_url=ollama_base)
            logger.info("本地 Ollama 已连接")
        except Exception as e:
            logger.warning(f"Ollama 连接失败: {e}")
            _local_llm = None

    config = WorldConfig(tick_interval_seconds=2.0, save_interval_ticks=100)
    _world = WorldEngine(config)

    _dialogue_mgr = DialogueManager(
        llm=_local_llm or _llm,
        world=_world,
        archiver=None,
        retriever=None,
    )

    _memory_archiver = MemoryArchiver(
        cloud_llm=_llm,
        local_llm=_local_llm,
        chroma_client=None,
        forgetting_curves=_agent_forgetting_curves,
    )

    _memory_retriever = MemoryRetriever(
        local_llm=_local_llm or _llm,
        embedder=None,
        chroma_client=None,
    )

    logger.info("V0.7 服务器初始化完成")
    yield

    logger.info("V0.7 服务器关闭")


app = FastAPI(title="Athenaeum V0.7", lifespan=lifespan)

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
    return {"status": "healthy", "version": "0.7"}


@ app.post("/world/create")
async def create_world(req: WorldCreateRequest):
    global _world

    for loc_name in req.locations:
        loc_id = loc_name.lower().replace(" ", "_")
        _world.register_location(Location(id=loc_id, name=loc_name))

    logger.info(f"世界已创建: {req.name}, 地点: {req.locations}")
    return {"message": "世界创建成功", "world": req.name}


@ app.post("/agent/create")
async def create_agent(req: AgentCreateRequest):
    global _world, _llm, _local_llm, _memory_archiver, _memory_retriever, _agent_forgetting_curves

    agent_id = req.id
    personality = req.personality or {
        "openness": 0.6,
        "conscientiousness": 0.7,
        "extraversion": 0.5,
        "agreeableness": 0.6,
        "neuroticism": 0.3,
    }

    if agent_id not in _agent_forgetting_curves:
        _agent_forgetting_curves[agent_id] = ForgettingCurve(agent_id)

    agent = V07Agent(
        agent_id=agent_id,
        name=req.name,
        personality=personality,
        occupation=req.occupation,
        soul=req.soul or {},
        llm=_local_llm or _llm,
        world=_world,
        initial_location=req.initial_location,
        cloud_llm=_llm,
        local_llm=_local_llm,
        archiver=_memory_archiver,
        retriever=_memory_retriever,
        forgetting_curve=_agent_forgetting_curves[agent_id],
    )

    _world.register_agent(agent_id, req.name, req.initial_location)
    logger.info(f"角色已创建: {req.name} ({agent_id})")

    return {"message": "角色创建成功", "agent_id": agent_id, "name": req.name}


@ app.post("/world/start")
async def start_world():
    global _engine_running, _tick_task

    if _engine_running:
        return {"message": "世界已在运行中"}

    _engine_running = True
    _tick_task = asyncio.create_task(_run_world_tick())

    return {"message": "世界已启动"}


@ app.post("/world/stop")
async def stop_world():
    global _engine_running, _tick_task

    _engine_running = False
    if _tick_task:
        _tick_task.cancel()

    return {"message": "世界已停止"}


@ app.post("/dialogue/start")
async def start_dialogue(agent_a: str, agent_b: str):
    global _dialogue_mgr, _world

    if not _world:
        raise HTTPException(status_code=400, detail="世界未创建")

    await _dialogue_mgr.trigger_dialogue(agent_a, agent_b, _world._agent_registry)
    return {"message": f"对话已开始: {agent_a} <-> {agent_b}"}


async def _run_world_tick():
    global _world, _engine_running

    while _engine_running:
        try:
            _world.advance_tick()
            await asyncio.sleep(_world._config.tick_interval_seconds)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Tick 执行错误: {e}")


@ app.get("/world/state")
async def get_world_state():
    """获取世界状态"""
    global _world, _dialogue_mgr

    if not _world:
        return {"tick_id": 0, "time_of_day": "unknown", "weather": "unknown", "agents": [], "locations": [], "dialogues": []}

    agents_data = []
    if hasattr(_world, '_agents'):
        for agent_id, agent_data in _world._agents.items():
            agents_data.append({
                "id": agent_id,
                "name": _world.agent_names.get(agent_id, agent_id),
                "location": getattr(agent_data, 'location_id', 'unknown') if isinstance(agent_data, object) else str(agent_data),
            })

    recent_dialogues = _dialogue_mgr._sessions.values().__iter__().__next__().conversation_log[-20:] if _dialogue_mgr._sessions else []

    return {
        "tick_id": getattr(_world, '_tick_id', 0),
        "time_of_day": str(getattr(_world, '_time_of_day', 'unknown')),
        "weather": str(getattr(_world, '_weather', 'unknown')),
        "agents": agents_data,
        "locations": list(_world.get_all_locations().keys()) if hasattr(_world, 'get_all_locations') else [],
        "dialogues": [
            {"from": d.from_agent, "to": d.to_agent, "utterance": d.utterance, "micro_action": getattr(d, 'micro_action', None), "tick": getattr(d, 'tick', 0)}
            for d in recent_dialogues
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
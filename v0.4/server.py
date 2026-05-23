"""
server.py — V0.4 世界工坊 API 服务器
在 V0.3 基础上新增 worldsmith 路由
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
project_root = current_dir.parent  # /Volumes/Ollama-Models/Athenaeum

# 添加 V0.3 server 路径（包含 core 和 utils）
v03_server_path = project_root / "v0.3" / "server"
sys.path.insert(0, str(v03_server_path))

# 添加项目根路径
sys.path.insert(0, str(project_root))

from core.world_engine import WorldEngine, WorldConfig, Location
from core.dialogue_engine import DialogueManager
from core.agent import V03Agent, MinimalAgent
from core.world_generator import WorldGenerator
from utils.llm_client import LLMClient

# V0.4 世界工坊
sys.path.insert(0, str(current_dir))
from world_models import WorldsmithGenerateRequest, CharacterBatchRequest, RelationshipGenerateRequest
from worldsmith import Worldsmith

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_world: WorldEngine = None
_llm: LLMClient = None
_dialogue_mgr: DialogueManager = None
_local_llm = None
_worldsmith: Worldsmith = None
_ws_clients: list = []
_possessed_agent: str = None
_engine_running: bool = False
_tick_task: asyncio.Task = None
_generated_relationships: list = []  # 存储生成的关系数据


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _world, _llm, _dialogue_mgr, _local_llm, _worldsmith, _engine_running, _tick_task

    use_ollama = os.environ.get("USE_OLLAMA", "").lower() in ("1", "true", "yes")

    _engine_running = False
    _tick_task = None

    if use_ollama:
        from utils.ollama_client import OllamaLLMClient
        _llm = OllamaLLMClient()
        _local_llm = _llm
        logger.info("[Server] 使用本地 Ollama (qwen3.5:4b)")
    else:
        # 尝试创建本地 Ollama 客户端作为 fallback
        try:
            from utils.ollama_client import OllamaLLMClient
            _local_llm = OllamaLLMClient()
            # 将 Ollama 作为 fallback 传入 MiniMax 客户端
            _llm = LLMClient(fallback_llm=_local_llm)
            logger.info("[Server] 使用云端 LLM (MiniMax)，fallback: 本地 Ollama")
            # 启动时检查云端可用性
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
    _dialogue_mgr = DialogueManager(_local_llm or _llm, _world)
    _world.set_dialogue_manager(_dialogue_mgr)

    # 不再自动初始化默认世界，等待用户在世界工坊创建

    # 世界工坊
    _worldsmith = Worldsmith(_llm, _local_llm)

    logger.info("[Server] V0.4 世界工坊已就绪，请先创建世界再启动引擎")
    yield
    logger.info("[Server] 关闭中...")


def _setup_default_world():
    _world.register_location(Location("tavern", "酒馆", ["indoor", "social"], 10))
    _world.register_location(Location("square", "广场", ["outdoor", "public"], 20))
    _world.register_location(Location("house_alex", "亚历山大宅", ["indoor", "private"], 5))
    _world.register_location(Location("house_maria", "玛丽亚宅", ["indoor", "private"], 5))
    _world.register_location(Location("bakery", "面包店", ["indoor", "commercial"], 8))

    _world.register_agent("alex", "亚历山大", "house_alex")
    _world.register_agent("maria", "玛丽亚", "house_alex")
    _world.register_agent("bakery_owner", "面包师", "bakery")

    _world.register_v03_agent("alex", V03Agent(
        agent_id="alex", name="亚历山大",
        personality={"openness": 0.6, "conscientiousness": 0.7, "extraversion": 0.5, "agreeableness": 0.6, "neuroticism": 0.3},
        llm=_llm, world=_world, initial_location="house_alex",
    ))
    _world.register_v03_agent("maria", V03Agent(
        agent_id="maria", name="玛丽亚",
        personality={"openness": 0.7, "conscientiousness": 0.5, "extraversion": 0.8, "agreeableness": 0.7, "neuroticism": 0.2},
        llm=_llm, world=_world, initial_location="house_maria",
    ))
    _world.register_v03_agent("bakery_owner", MinimalAgent(
        agent_id="bakery_owner", name="面包师", world=_world, llm=_llm,
    ))
    _world.start_agents()


async def _tick_loop():
    while True:
        try:
            result = await _world.tick()
            await _broadcast_ws(result)
            await asyncio.sleep(_world.config.tick_interval_seconds)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"[Tick Loop] 错误: {e}")


async def _broadcast_ws(data: dict):
    if not _ws_clients:
        return
    for client in _ws_clients[:]:
        try:
            await client.send_json(data)
        except Exception:
            _ws_clients.remove(client)


app = FastAPI(title="World Pulse API", version="0.4.0", lifespan=lifespan)

static_dir = project_root / "v0.3" / "client" / "dist"
app.mount("/assets", StaticFiles(directory=str(static_dir / "assets")), name="assets")
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

worldsmith_static_dir = project_root / "v0.4" / "worldsmith_client" / "dist"
app.mount("/worldsmith/assets", StaticFiles(directory=str(worldsmith_static_dir / "assets")), name="worldsmith_assets")


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


@app.get("/")
async def root():
    index_path = static_dir / "index.html"
    if index_path.exists():
        from fastapi.responses import FileResponse
        return FileResponse(index_path)
    return {"message": "World Pulse V0.4 API", "version": "0.4.0"}


@app.get("/worldsmith")
async def worldsmith():
    ws_index_path = worldsmith_static_dir / "index.html"
    if ws_index_path.exists():
        from fastapi.responses import FileResponse
        return FileResponse(ws_index_path)
    return {"message": "Worldsmith V0.4", "status": "not found"}


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
    """
    完整世界工坊流程：
    1. 生成世界骨架
    2. 生成角色（含 introduce_text）
    3. 编织关系（含视角校验）
    """
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
    global _engine_running, _tick_task, _generated_relationships

    world_data = req.get("world", {})
    characters = req.get("characters", [])
    relationships = req.get("relationships", [])

    await _world.reset_world(world_data, characters, _local_llm or _llm)
    _generated_relationships = relationships  # 保存关系数据

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


@app.get("/characters/{char_id}/introduce_text")
async def regenerate_introduce_text(char_id: str, characters: list[dict]):
    """重新为某个角色生成 introduce_text"""
    from world_models import CharacterConfig
    char = next((c for c in characters if c["id"] == char_id), None)
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")
    config = CharacterConfig(**char)
    updated = await _worldsmith._generate_introduce_texts([config])
    return {"introduce_text": updated[0].introduce_text}


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


# -------------------------------------------------------------------------
# V0.3 原有路由（保留）
# -------------------------------------------------------------------------

@app.post("/agent/move")
async def move_agent(agent_id: str, target_location: str):
    success = _world.move_agent(agent_id, target_location)
    if not success:
        raise HTTPException(status_code=400, detail="移动失败")
    return {"success": True}


@app.post("/agent/possess")
async def possess_agent(agent_id: str, message: str):
    global _possessed_agent
    _possessed_agent = agent_id
    for session_pair, session in _dialogue_mgr._sessions.items():
        if agent_id in session_pair:
            session.possess(agent_id, message)
            break
    return {"success": True, "possessed": agent_id}


@app.post("/agent/release")
async def release_possession():
    global _possessed_agent
    _possessed_agent = None
    for session in _dialogue_mgr._sessions.values():
        session.release()
    return {"success": True}


@app.get("/dialogue/active")
async def get_active_dialogues():
    return {
        "active_agents": list(_dialogue_mgr._active_agents),
        "session_count": len(_dialogue_mgr._sessions),
    }


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

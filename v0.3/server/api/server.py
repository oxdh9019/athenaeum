"""
server.py — V0.3 FastAPI 主服务器
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

current_dir = Path(__file__).parent.parent
sys.path.insert(0, str(current_dir))

from core.world_engine import WorldEngine, WorldConfig, Location
from core.dialogue_engine import DialogueManager
from core.agent import V03Agent, MinimalAgent
from core.world_generator import WorldGenerator
from utils.llm_client import LLMClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_world: WorldEngine = None
_llm: LLMClient = None
_dialogue_mgr: DialogueManager = None
_ws_clients: list[WebSocket] = []
_possessed_agent: str = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _world, _llm, _dialogue_mgr

    import os
    use_ollama = os.environ.get("USE_OLLAMA", "").lower() in ("1", "true", "yes")

    if use_ollama:
        from utils.ollama_client import OllamaLLMClient
        _llm = OllamaLLMClient()
        logger.info("[Server] 使用本地 Ollama (qwen3.5:4b)")
    else:
        _llm = LLMClient()
        logger.info("[Server] 使用云端 LLM")

    config = WorldConfig(
        tick_interval_seconds=2.0,
        save_interval_ticks=100,
    )
    _world = WorldEngine(config)

    _dialogue_mgr = DialogueManager(_llm, _world)
    _world.set_dialogue_manager(_dialogue_mgr)

    _setup_default_world()

    asyncio.create_task(_tick_loop())

    logger.info("[Server] V0.3 世界引擎已启动")
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
        agent_id="alex",
        name="亚历山大",
        personality={"openness": 0.6, "conscientiousness": 0.7, "extraversion": 0.5, "agreeableness": 0.6, "neuroticism": 0.3},
        llm=_llm,
        world=_world,
        initial_location="house_alex",
    ))
    _world.register_v03_agent("maria", V03Agent(
        agent_id="maria",
        name="玛丽亚",
        personality={"openness": 0.7, "conscientiousness": 0.5, "extraversion": 0.8, "agreeableness": 0.7, "neuroticism": 0.2},
        llm=_llm,
        world=_world,
        initial_location="house_maria",
    ))
    _world.register_v03_agent("bakery_owner", MinimalAgent(
        agent_id="bakery_owner",
        name="面包师",
        world=_world,
        llm=_llm,
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
    msg = JSONResponse(content=data)
    for client in _ws_clients[:]:
        try:
            await client.send_json(data)
        except Exception:
            _ws_clients.remove(client)


app = FastAPI(title="World Pulse API", version="0.3.0", lifespan=lifespan)

import os
from pathlib import Path
static_dir = Path(__file__).parent.parent.parent / "client" / "dist"
app.mount("/assets", StaticFiles(directory=str(static_dir / "assets")), name="assets")
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/")
async def serve_frontend():
    index_path = static_dir / "index.html"
    if index_path.exists():
        from fastapi.responses import FileResponse
        return FileResponse(index_path)
    return {"message": "World Pulse V0.3 API", "version": "0.3.0"}


class GenerateWorldRequest(BaseModel):
    description: str


class MoveAgentRequest(BaseModel):
    agent_id: str
    target_location: str


class PossessRequest(BaseModel):
    agent_id: str
    message: str


class LocationRequest(BaseModel):
    id: str
    name: str
    tags: list[str]
    capacity: int = 5


class AgentRequest(BaseModel):
    id: str
    name: str
    location_id: str


class WeatherRequest(BaseModel):
    weather: str


@app.get("/")
async def root():
    return {"message": "World Pulse V0.3 API", "version": "0.3.0"}


@app.get("/world/state")
async def get_world_state():
    return {
        "tick_id": _world._tick_id,
        "time": {
            "game_hour": _world._game_hour,
            "time_of_day": _world._time_of_day.value,
        },
        "weather": _world._weather.value,
        "agents": _world._serialize_agents(),
        "locations": _world._serialize_locations(),
        "recent_dialogues": _world._recent_dialogues[-20:],
        "recent_actions": _world._recent_actions[-15:],
    }


@app.post("/world/generate")
async def generate_world(req: GenerateWorldRequest):
    generator = WorldGenerator(_llm)
    world = await generator.generate_world(req.description)
    return world.model_dump()


@app.post("/agent/move")
async def move_agent(req: MoveAgentRequest):
    success = _world.move_agent(req.agent_id, req.target_location)
    if not success:
        raise HTTPException(status_code=400, detail="移动失败")
    return {"success": True}


@app.post("/agent/possess")
async def possess_agent(req: PossessRequest):
    global _possessed_agent
    _possessed_agent = req.agent_id
    for session_pair, session in _dialogue_mgr._sessions.items():
        if req.agent_id in session_pair:
            session.possess(req.agent_id, req.message)
            break
    return {"success": True, "possessed": req.agent_id}


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


@app.post("/world/save/{name}")
async def save_world(name: str):
    path = f"data/saves/{name}.json"
    await _world.save(path)
    return {"success": True, "path": path}


@app.post("/world/load/{name}")
async def load_world(name: str):
    path = f"data/saves/{name}.json"
    await _world.load(path)
    return {"success": True}


@app.post("/world/weather/set")
async def set_weather(req: WeatherRequest):
    _world.set_weather(req.weather)
    return {"success": True, "weather": req.weather}


@app.post("/world/locations/add")
async def add_location(req: LocationRequest):
    from core.world_engine import Location
    loc = Location(req.id, req.name, req.tags, req.capacity)
    _world.register_location(loc)
    return {"success": True}


@app.post("/world/agents/add")
async def add_agent(req: AgentRequest):
    _world.register_agent(req.id, req.name, req.location_id)
    return {"success": True}


@app.delete("/world/agents/{agent_id}")
async def remove_agent(agent_id: str):
    success = _world.remove_agent(agent_id)
    if not success:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"success": True}


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

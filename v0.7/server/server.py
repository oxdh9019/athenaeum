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


@ app.post("/world/generate_full")
async def generate_full_world(req: WorldGenerateRequest):
    """
    生成完整世界：世界描述 + 角色 + 关系 + 性格提示
    使用 LLM 生成
    """
    global _llm, _local_llm

    # 选择模型：优先使用请求指定的模型，否则尝试本地再云端
    llm = None
    model_preference = getattr(req, 'model', None)
    if model_preference == 'local' and _local_llm:
        llm = _local_llm
    elif model_preference == 'cloud' and _llm:
        # 云端需要检查是否真的可用（API Key 是否配置）
        if not _llm._api_key:
            return {"error": "云端 MiniMax API 未配置 API Key。请设置 MINIMAX_API_KEY 或 ANTHROPIC_API_KEY 环境变量。"}
        llm = _llm
    elif model_preference == 'cloud':
        return {"error": "云端 MiniMax API 未配置。请检查 API Key 环境变量。"}
    else:
        llm = _local_llm or _llm

    if not llm:
        return {"error": "无可用的 LLM 模型。请确保 Ollama 本地模型或云端 API 已配置。"}

    prompt = f"""你是一个世界构建专家。根据以下描述，生成一个详细的世界设定和角色。

世界描述：{req.description}

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
        # 解析 JSON
        import json
        # 尝试提取 JSON
        start = content.find('{')
        end = content.rfind('}') + 1
        if start != -1 and end > start:
            json_str = content[start:end]
            try:
                data = json.loads(json_str)
                return data
            except json.JSONDecodeError as e:
                logger.warning(f"JSON 解析部分失败，尝试修复: {e}")
                # 尝试修复常见的 JSON 问题
                # 1. 移除尾随逗号
                import re
                json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
                try:
                    data = json.loads(json_str)
                    return data
                except:
                    pass
                # 2. 尝试在整个 content 中找 JSON
                all_matches = list(re.finditer(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', json_str))
                if all_matches:
                    for match in reversed(all_matches):
                        try:
                            data = json.loads(match.group())
                            return data
                        except:
                            continue
                return {"error": "生成失败，JSON 解析错误", "raw": content[:500]}
        else:
            return {"error": "生成失败，无法解析响应", "raw": content[:500]}
    except Exception as e:
        logger.error(f"世界生成失败: {e}")
        return {"error": str(e)}


@ app.post("/world/apply")
async def apply_world(req: WorldApplyRequest):
    """
    将生成的世界和角色应用到引擎
    """
    global _world

    if not _world:
        raise HTTPException(status_code=400, detail="世界未创建，请先调用 /world/create")

    try:
        # 应用地点
        world_data = req.world
        for loc in world_data.get('locations', []):
            _world.register_location(Location(
                id=loc.get('id', loc.get('name', '').lower().replace(' ', '_')),
                name=loc.get('name', ''),
            ))

        # 应用角色
        for char in req.characters:
            agent_id = char.get('id', char.get('name', '').lower().replace(' ', '_'))
            _world.register_agent(agent_id, char.get('name', ''), char.get('initial_location', '图书馆'))

        logger.info(f"世界已应用: {world_data.get('name', 'unknown')}, {len(req.characters)} 个角色")
        return {"message": f"世界'{world_data.get('name', '')}'已成功应用，{len(req.characters)}个角色已创建"}
    except Exception as e:
        logger.error(f"应用世界失败: {e}")
        return {"error": str(e)}


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
            await _world.tick()
            await asyncio.sleep(_world.config.tick_interval_seconds)
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
        "locations": [loc.name for loc in _world.get_all_locations()] if hasattr(_world, 'get_all_locations') else [],
        "dialogues": [
            {"from": d.from_agent, "to": d.to_agent, "utterance": d.utterance, "micro_action": getattr(d, 'micro_action', None), "tick": getattr(d, 'tick', 0)}
            for d in recent_dialogues
        ]
    }


@ app.post("/server/stop")
async def stop_server():
    """关闭服务器"""
    import os
    import signal
    logger.info("收到关闭指令，正在停止服务器...")
    # 发送 SIGTERM 给当前进程
    os.kill(os.getpid(), signal.SIGTERM)
    return {"message": "服务器已关闭"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
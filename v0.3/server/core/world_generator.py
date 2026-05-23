"""
world_generator.py — V0.3 AI 世界生成器
根据用户简短描述生成完整世界
"""

import asyncio
import logging
from typing import Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class GeneratedLocation(BaseModel):
    id: str
    name: str
    description: str
    tags: list[str]
    capacity: int


class GeneratedCharacter(BaseModel):
    id: str
    name: str
    age: int
    gender: str
    personality: dict
    backstory: str
    initial_location: str


class GeneratedWorld(BaseModel):
    name: str
    description: str
    locations: list[GeneratedLocation]
    characters: list[GeneratedCharacter]
    relationships: list[dict]


class WorldGenerator:
    """
    AI 世界生成器
    支持多步骤生成：地点 → 角色槽位 → 丰满角色 → 编织关系
    """

    def __init__(self, llm):
        self._llm = llm

    async def generate_world(self, user_description: str) -> GeneratedWorld:
        """
        根据用户描述生成完整世界
        """
        logger.info(f"[WorldGenerator] 开始生成世界: {user_description}")

        locations = await self._generate_locations(user_description)
        logger.info(f"[WorldGenerator] 生成地点: {len(locations)} 个")

        character_slots = await self._generate_character_slots(user_description, locations)
        logger.info(f"[WorldGenerator] 生成角色槽位: {len(character_slots)} 个")

        characters = await self._generate_characters(character_slots)
        logger.info(f"[WorldGenerator] 生成角色: {len(characters)} 个")

        relationships = await self._generate_relationships(characters)
        logger.info(f"[WorldGenerator] 生成关系: {len(relationships)} 条")

        world = GeneratedWorld(
            name="生成的世界",
            description=user_description,
            locations=locations,
            characters=characters,
            relationships=relationships,
        )

        return world

    async def _generate_locations(self, description: str) -> list[GeneratedLocation]:
        prompt = f"""根据以下描述，生成4-6个地点：

描述：{description}

请生成地点列表，输出JSON格式：
{{"locations": [
  {{"id": "location_1", "name": "地点名", "description": "描述", "tags": ["indoor", "social"], "capacity": 5}}
]}}

地点应该多样化，包含不同类型（室内/室外、公共/私人等）。
"""

        try:
            response = await self._llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=500,
            )
            import json
            import re
            match = re.search(r'\{[^}]+\}', response)
            if match:
                data = json.loads(match.group())
                locations = []
                for loc in data.get("locations", []):
                    locations.append(GeneratedLocation(**loc))
                return locations
        except Exception as e:
            logger.error(f"地点生成失败: {e}")

        return self._default_locations()

    async def _generate_character_slots(
        self, description: str, locations: list[GeneratedLocation]
    ) -> list[dict]:
        location_names = ", ".join([loc.name for loc in locations])
        prompt = f"""根据以下世界描述，生成角色配置：

世界：{description}
地点：{location_names}

请生成3-5个角色槽位，输出JSON格式：
{{"characters": [
  {{"name": "角色名", "age": 30, "gender": "男/女", "role_type": "商人/居民/访客等", "initial_location": "地点名"}}
]}}
"""

        try:
            response = await self._llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=500,
            )
            import json
            import re
            match = re.search(r'\{[^}]+\}', response)
            if match:
                data = json.loads(match.group())
                return data.get("characters", [])
        except Exception as e:
            logger.error(f"角色槽位生成失败: {e}")

        return []

    async def _generate_characters(self, slots: list[dict]) -> list[GeneratedCharacter]:
        characters = []
        for i, slot in enumerate(slots):
            character = await self._generate_single_character(slot, i)
            if character:
                characters.append(character)
        return characters

    async def _generate_single_character(self, slot: dict, index: int) -> Optional[GeneratedCharacter]:
        prompt = f"""请为以下角色槽位生成完整角色信息：

姓名：{slot.get('name', f'角色{index}')}
年龄：{slot.get('age', 30)}
性别：{slot.get('gender', '未知')}
类型：{slot.get('role_type', '居民')}
初始位置：{slot.get('initial_location', '未知')}

请生成角色的完整信息（Big Five性格用0-1之间的小数，backstory不超过100字）：
输出JSON格式：
{{"id": "char_{index}", "name": "姓名", "age": 年龄, "gender": "性别", 
  "personality": {{"openness": 0.5, "conscientiousness": 0.5, "extraversion": 0.5, "agreeableness": 0.5, "neuroticism": 0.5}},
  "backstory": "背景故事", "initial_location": "初始位置"}}
"""

        try:
            response = await self._llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=300,
            )
            import json
            import re
            match = re.search(r'\{[^}]+\}', response)
            if match:
                data = json.loads(match.group())
                return GeneratedCharacter(**data)
        except Exception as e:
            logger.error(f"角色 {slot.get('name')} 生成失败: {e}")

        return GeneratedCharacter(
            id=f"char_{index}",
            name=slot.get('name', f'角色{index}'),
            age=slot.get('age', 30),
            gender=slot.get('gender', '未知'),
            personality={"openness": 0.5, "conscientiousness": 0.5, "extraversion": 0.5, "agreeableness": 0.5, "neuroticism": 0.5},
            backstory="一个普通的居民",
            initial_location=slot.get('initial_location', '未知'),
        )

    async def _generate_relationships(self, characters: list[GeneratedCharacter]) -> list[dict]:
        if len(characters) < 2:
            return []

        char_names = ", ".join([c.name for c in characters])
        prompt = f"""请为以下角色之间生成关系：

角色：{char_names}

请生成角色之间的关系，输出JSON格式：
{{"relationships": [
  {{"from": "角色A", "to": "角色B", "type": "朋友/家人/邻居/陌生人等", "strength": 0.5}}
]}}

关系应该多样化。
"""

        try:
            response = await self._llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=300,
            )
            import json
            import re
            match = re.search(r'\{[^}]+\}', response)
            if match:
                data = json.loads(match.group())
                return data.get("relationships", [])
        except Exception as e:
            logger.error(f"关系生成失败: {e}")

        return []

    def _default_locations(self) -> list[GeneratedLocation]:
        return [
            GeneratedLocation(id="loc_tavern", name="酒馆", description="村里唯一的酒馆", tags=["indoor", "social"], capacity=10),
            GeneratedLocation(id="loc_square", name="广场", description="村子中心的广场", tags=["outdoor", "public"], capacity=20),
            GeneratedLocation(id="loc_house1", name="民居A", description="简朴的民居", tags=["indoor", "private"], capacity=4),
            GeneratedLocation(id="loc_house2", name="民居B", description="另一间民居", tags=["indoor", "private"], capacity=4),
        ]

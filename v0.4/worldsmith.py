"""
worldsmith.py — V0.4 世界工坊
基于自然语言的世界与角色批量生成 + Web 审核界面后端
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import re
from typing import Optional

from world_models import (
    GeneratedWorld, WorldAtmosphere, LocationModel, WorldTimeRules,
    CharacterConfig, BigFivePersonality, ExtendedPersonality,
    NeedItem, CharacterBackstory, CharacterPairRelationship,
    SharedHistoryValidation, GenerationMetrics, WorldsmithGenerateRequest,
    CharacterBatchRequest, RelationshipGenerateRequest,
)

logger = logging.getLogger(__name__)


class Worldsmith:
    """
    V0.4 世界工坊核心
    双层模型策略:
    - 云端 MiniMax: 世界骨架、角色完整配置、关系编织
    - 本地 Qwen: 去重校验、性格提示、introduce_text
    """

    def __init__(self, cloud_llm, local_llm):
        self._cloud = cloud_llm
        self._local = local_llm
        self._metrics = GenerationMetrics()

    @property
    def metrics(self) -> GenerationMetrics:
        return self._metrics

    # =============================================================================
    # 世界生成 (云端 MiniMax)
    # =============================================================================

    async def generate_world(self, description: str) -> GeneratedWorld:
        """
        调用云端生成世界骨架，然后本地校验
        """
        logger.info(f"[Worldsmith] 生成世界: {description[:50]}...")

        prompt = self._build_world_prompt(description)
        response = await self._cloud.chat(
            messages=[{"role": "user", "content": prompt}],
            system=self._world_system_prompt(),
            temperature=0.7,
            max_tokens=3000,
        )

        logger.info(f"[Worldsmith] 世界生成响应长度: {len(response)}")
        logger.info(f"[Worldsmith] 世界生成响应前1000字符: {response[:1000]}")

        try:
            world = self._parse_world_response(response)
        except Exception as e:
            logger.error(f"[Worldsmith] 世界解析失败: {e}")
            logger.error(f"[Worldsmith] 异常响应: {response[:1000] if response else 'empty'}")
            raise  # 不再回退到默认世界，直接抛出异常

        # 本地 Qwen 校验
        world = await self._validate_world(world)

        logger.info(f"[Worldsmith] 世界生成完成: {world.name}, {len(world.locations)} 个地点")
        return world

    def _generate_default_world(self, description: str) -> GeneratedWorld:
        """生成默认世界（当云端生成失败时使用）"""
        default_locations = [
            LocationModel(id="library", name="图书馆", description="安静的阅读场所", tags=["indoor", "social"], capacity=10),
            LocationModel(id="bakery", name="面包店", description="香气四溢的面包店", tags=["indoor", "commercial"], capacity=8),
            LocationModel(id="square", name="广场", description="热闹的公共广场", tags=["outdoor", "public"], capacity=20),
            LocationModel(id="tavern", name="酒馆", description="旅行者聚集的酒馆", tags=["indoor", "social"], capacity=15),
            LocationModel(id="house1", name="民居", description="小镇居民的住所", tags=["indoor", "private"], capacity=5),
        ]
        
        return GeneratedWorld(
            name="翡翠小镇",
            description=description,
            locations=default_locations,
            time_rules=WorldTimeRules(day_start_hour=8, day_end_hour=22, tick_interval_minutes=60),
            atmosphere=WorldAtmosphere(
                mood="宁静祥和",
                dominant_themes=["社区", "传统", "日常生活"],
                ambient_sounds=["鸟鸣", "风声", "远处的钟声"]
            )
        )

    def _build_world_prompt(self, description: str) -> str:
        return f"""根据以下描述，生成一个完整的世界设定：

描述：{description}

请生成包含以下内容的世界JSON：
{{
  "name": "世界名称",
  "description": "世界概述",
  "locations": [
    {{
      "id": "loc_id",
      "name": "地点名称",
      "description": "地点描述",
      "tags": ["室内/室外", "公共/私人", "社交/安静"],
      "capacity": 最大人数
    }}
  ],
  "time_rules": {{
    "day_start_hour": 8,
    "day_end_hour": 22,
    "tick_interval_minutes": 60
  }},
  "atmosphere": {{
    "mood": "整体氛围",
    "dominant_themes": ["主题1", "主题2"],
    "ambient_sounds": ["环境音1", "环境音2"]
  }}
}}

地点应该多样化，包含4-6个不同类型。请严格输出JSON。"""

    def _world_system_prompt(self) -> str:
        return """你是一个世界设定生成专家。请严格按JSON格式输出，不要包含任何其他文字。"""

    def _parse_world_response(self, response: str) -> GeneratedWorld:
        """从响应中提取 JSON 并解析为 GeneratedWorld"""
        try:
            json_str = self._extract_json(response)
            logger.info(f"[Worldsmith] 提取的JSON长度: {len(json_str)}")
            logger.info(f"[Worldsmith] 提取的JSON前500字符: {json_str[:500]}")
            data = json.loads(json_str)

            logger.info(f"[Worldsmith] JSON数据键: {list(data.keys())}")
            logger.info(f"[Worldsmith] locations数量: {len(data.get('locations', []))}")

            locations_raw = data.get("locations", [])
            logger.info(f"[Worldsmith] locations原始数据: {locations_raw}")
            logger.info(f"[Worldsmith] locations类型: {type(locations_raw)}")
            if isinstance(locations_raw, list):
                locations = [
                    LocationModel(**loc) for loc in locations_raw
                ]
                logger.info(f"[Worldsmith] 解析后locations数量: {len(locations)}")
            else:
                logger.warning(f"[Worldsmith] locations不是数组，而是: {type(locations_raw)}, 值: {str(locations_raw)[:200]}")
                locations = []

            time_rules_data = data.get("time_rules", {})
            time_rules = WorldTimeRules(**time_rules_data)

            atmosphere_data = data.get("atmosphere", {})
            atmosphere = WorldAtmosphere(**atmosphere_data)

            return GeneratedWorld(
                name=data.get("name", "未知世界"),
                description=data.get("description", ""),
                locations=locations,
                time_rules=time_rules,
                atmosphere=atmosphere,
            )
        except Exception as e:
            logger.error(f"[Worldsmith] 世界解析失败: {e}")
            logger.error(f"[Worldsmith] 响应内容: {response[:1000]}")
            raise ValueError(f"世界解析失败: {e}") from e

    def _fix_json(self, json_str: str) -> str:
        """尝试修复损坏的 JSON 字符串"""
        import json
        
        # 移除 markdown 代码块标记
        json_str = re.sub(r'^```json\s*', '', json_str, flags=re.MULTILINE)
        json_str = re.sub(r'^```\s*', '', json_str, flags=re.MULTILINE)
        
        # 移除前后可能存在的非JSON文本
        first_brace = json_str.find('{')
        last_brace = json_str.rfind('}')
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            json_str = json_str[first_brace:last_brace+1]
        
        # 移除单行注释
        json_str = re.sub(r'//[^\n]*', '', json_str)
        
        # 移除多行注释
        json_str = re.sub(r'/\*[\s\S]*?\*/', '', json_str)
        
        # 尝试解析
        try:
            json.loads(json_str)
            return json_str
        except json.JSONDecodeError:
            pass
        
        # 尝试处理常见的尾部逗号问题
        json_str = re.sub(r',\s*\}', '}', json_str)
        json_str = re.sub(r',\s*\]', ']', json_str)
        
        try:
            json.loads(json_str)
            return json_str
        except json.JSONDecodeError:
            pass
        
        # 尝试修复引号问题
        json_str = json_str.replace('""', '"')
        
        try:
            json.loads(json_str)
            return json_str
        except json.JSONDecodeError:
            pass
        
        raise ValueError("无法修复JSON")

    def _extract_json(self, text: str, expected_keys: list[str] = None) -> str:
        """从响应中提取 JSON 字符串

        Args:
            text: 原始响应文本
            expected_keys: 期望的 JSON 键列表，用于验证提取结果
        """
        import json

        original_len = len(text)
        logger.info(f"[Worldsmith] _extract_json 输入长度: {original_len}")

        # 步骤1: 清理 [THINK]...[/THINK] 块（精确匹配，不跨代码块）
        text = re.sub(r'\[THINK\].*?\[/THINK\]', '', text, flags=re.DOTALL | re.IGNORECASE)

        # 步骤2: 移除 markdown 代码块 ```json ... ``` 和 ``` ... ```
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)

        # 步骤3: 移除 [SPEAK] 和 [/SPEAK] 标签（但保留标签内的 JSON 内容）
        text = re.sub(r'\[/?SPEAK\]', '', text, flags=re.IGNORECASE)

        # 步骤4: 跳过前导空白和换行
        text = text.lstrip('\n\r\t ')

        logger.info(f"[Worldsmith] 清理后文本长度: {len(text)}, 前100字符: {text[:100]}")

        # 如果没有期望的键，默认验证 characters/locations/from_id
        if expected_keys is None:
            expected_keys = ["characters", "locations", "from_id"]

        # 策略A: 直接查找已知模式
        for pattern in [
            r'\{\s*"characters"\s*:\s*\[',  # 角色生成
            r'\{\s*"locations"\s*:\s*\[',  # 世界生成
            r'\{\s*"from_id"\s*:',  # 关系生成
            r'\{\s*"tips"\s*:',  # 性格提示
        ]:
            match = re.search(pattern, text)
            if match:
                start = match.start()
                json_str = self._extract_json_by_bracket_matching(text[start:])
                if json_str:
                    try:
                        data = json.loads(json_str)
                        # 验证是否包含期望的键
                        found_key = next((k for k in expected_keys if k in data), None)
                        if found_key:
                            logger.info(f"[Worldsmith] 策略A找到 {found_key}: {str(data.get(found_key, ''))[:100]}")
                            return json_str
                    except json.JSONDecodeError:
                        pass

        # 策略B: 查找任何 {" 开头并尝试提取
        for match in re.finditer(r'\{\s*"', text):
            start = match.start()
            json_str = self._extract_json_by_bracket_matching(text[start:])
            if json_str:
                try:
                    data = json.loads(json_str)
                    # 至少包含 expected_keys 中的一个
                    found_key = next((k for k in expected_keys if k in data), None)
                    if found_key:
                        logger.info(f"[Worldsmith] 策略B找到 {found_key}")
                        return json_str
                except json.JSONDecodeError:
                    pass

        logger.warning(f"[Worldsmith] JSON提取失败，清理后内容: {text[:300]}")
        raise ValueError(f"无法从响应中提取有效JSON，清理后内容: {text[:500]}")

    def _extract_json_by_bracket_matching(self, text: str) -> str:
        """通过括号匹配提取完整的 JSON 字符串

        使用栈式匹配，正确处理嵌套结构。
        """
        import json

        # 预处理：跳过前导空白
        text = text.lstrip('\n\r\t ')

        if not text or text[0] != '{':
            return ""

        # 记录所有括号的位置和深度
        stack = []  # [(pos, char, depth_at_open)]
        depth = 0

        for i, char in enumerate(text):
            if char in '{[':
                # 入栈
                stack.append((i, char, depth))
                depth += 1
            elif char in '}]':
                if stack and depth > 0:
                    # 出栈并匹配
                    open_pos, open_char, _ = stack.pop()
                    depth -= 1

                    # 如果深度回到 0，找到完整的 JSON
                    if depth == 0:
                        json_str = text[open_pos:i+1]

                        # 验证是否是有效 JSON
                        try:
                            json.loads(json_str)
                            return json_str
                        except json.JSONDecodeError:
                            # 尝试修复常见的 JSON 尾部问题
                            pass

        # 如果栈式匹配失败，尝试找最后一个有效的 JSON 片段
        logger.warning(f"[Worldsmith] bracket matching 未找到完整 JSON，尝试 fallback，长度: {len(text)}")

        # 尝试移除尾部截断的内容
        last_valid_pos = -1
        for i in range(len(text) - 1, -1, -1):
            if text[i] in '}]':
                try:
                    json_str = text[:i+1]
                    json.loads(json_str)
                    last_valid_pos = i
                    break
                except:
                    continue

        if last_valid_pos >= 0:
            logger.info(f"[Worldsmith] fallback 找到有效 JSON 尾部位置: {last_valid_pos}")
            return text[:last_valid_pos+1]

        # 从头开始找最长有效 JSON
        valid_json = ""
        for i in range(1, len(text) + 1):
            try:
                json_str = text[:i]
                json.loads(json_str)
                valid_json = json_str  # 保持最后一个有效的结果
            except json.JSONDecodeError:
                break

        if valid_json:
            logger.info(f"[Worldsmith] fallback 找到有效 JSON，长度: {len(valid_json)}")
            return valid_json

        return ""

    # =============================================================================
    # 本地 Qwen 校验
    # =============================================================================

    async def _validate_world(self, world: GeneratedWorld) -> GeneratedWorld:
        """本地 Qwen 校验: location 名称不重复"""
        if not world.locations:
            return world

        names = [loc.name for loc in world.locations]
        unique_names = set(names)

        if len(names) != len(unique_names):
            logger.warning("[Worldsmith] 检测到重复的地点名称，尝试去重")
            seen = {}
            for loc in world.locations:
                if loc.name in seen:
                    loc.name = f"{loc.name}_{seen[loc.name]}"
                    seen[loc.name] += 1
                else:
                    seen[loc.name] = 1

        return world

    async def _validate_character_names(
        self, characters: list[CharacterConfig]
    ) -> list[CharacterConfig]:
        """本地 Qwen 检查角色名/职业是否重复"""
        names = [c.name for c in characters]
        if len(names) != len(set(names)):
            logger.warning("[Worldsmith] 检测到重复角色名")

        # 检查职业重复
        roles = [c.identity_tags.primary for c in characters]
        if len(roles) != len(set(roles)):
            logger.info("[Worldsmith] 部分角色职业重复，可作为社交张力")

        return characters

    # =============================================================================
    # 角色批量生成 (云端 + 本地)
    # =============================================================================

    async def generate_characters(self, request: CharacterBatchRequest) -> list[CharacterConfig]:
        """
        调用云端 MiniMax 一次性生成 N 个角色完整配置
        调用本地 Qwen 为每个角色生成 introduce_text
        """
        logger.info(f"[Worldsmith] 批量生成 {request.num_characters} 个角色")
        logger.info(f"[Worldsmith] 世界设定: {request.world_description}")

        # 云端生成完整角色配置
        cloud_prompt = self._build_character_prompt(request)
        logger.info(f"[Worldsmith] 发送请求到云端 LLM，prompt 长度: {len(cloud_prompt)}")

        response = await self._cloud.chat(
            messages=[{"role": "user", "content": cloud_prompt}],
            system=self._character_system_prompt(),
            temperature=0.7,
            max_tokens=16000,  # 足够生成 10 个角色配置
        )

        logger.info(f"[Worldsmith] 云端响应长度: {len(response)}, 内容: {response[:500]}...")

        try:
            json_str = self._extract_json(response)
            logger.info(f"[Worldsmith] JSON提取成功，长度: {len(json_str)}")

            data = json.loads(json_str)
            chars_data = data.get("characters", [])
            logger.info(f"[Worldsmith] 找到 {len(chars_data)} 个角色数据")

            characters = self._parse_characters_response(json_str, request.locations)
            if not characters:
                logger.error(f"[Worldsmith] 解析结果为空，chars_data长度: {len(chars_data)}")
                logger.error(f"[Worldsmith] 完整响应: {response[:2000]}")
                raise ValueError("角色解析失败：解析结果为空")
            logger.info(f"[Worldsmith] 成功解析 {len(characters)} 个角色")
        except ValueError:
            raise  # 已经是 ValueError，直接重新抛出
        except Exception as e:
            logger.error(f"[Worldsmith] 角色解析失败: {e}")
            logger.error(f"[Worldsmith] 异常响应: {response[:1000] if response else 'empty'}")
            raise ValueError(f"角色解析失败: {str(e)[:200]}") from None

        # 本地 Qwen 去重校验
        characters = await self._validate_character_names(characters)

        # 本地 Qwen 生成 introduce_text
        characters = await self._generate_introduce_texts(characters)

        logger.info(f"[Worldsmith] 角色生成完成: {len(characters)} 个")
        return characters

    def _generate_default_characters(self, num_characters: int, locations: list[str]) -> list[CharacterConfig]:
        """生成默认角色（当云端生成失败时使用）"""
        default_chars = [
            {
                "id": "char_1", "name": "艾琳", "age": 35, "gender": "女", "pronouns": "她",
                "identity_tags": {"primary": "图书馆管理员", "secondary": ["知识爱好者"], "self_identity": "知识守护者"},
                "personality": {"openness": 0.8, "conscientiousness": 0.9, "extraversion": 0.3, "agreeableness": 0.7, "neuroticism": 0.4},
                "extended_personality": {"empathy": 0.6, "humor": 0.3, "ambition": 0.4, "loyalty": 0.8, "courage": 0.5, "patience": 0.9, "generosity": 0.5},
                "backstory": {"title": "图书馆的守护者", "childhood": "在书堆中长大", "adulthood": "成为图书馆管理员", "present": "守护着小镇的知识宝库", "turning_points": []},
                "needs": [{"name": "safety", "level": 0.5}, {"name": "belonging", "level": 0.6}],
            },
            {
                "id": "char_2", "name": "马克", "age": 40, "gender": "男", "pronouns": "他",
                "identity_tags": {"primary": "面包师", "secondary": ["美食家"], "self_identity": "面团的魔法师"},
                "personality": {"openness": 0.5, "conscientiousness": 0.8, "extraversion": 0.6, "agreeableness": 0.9, "neuroticism": 0.2},
                "extended_personality": {"empathy": 0.7, "humor": 0.8, "ambition": 0.5, "loyalty": 0.7, "courage": 0.4, "patience": 0.8, "generosity": 0.9},
                "backstory": {"title": "温暖的面包师", "childhood": "跟着父亲学做面包", "adulthood": "开了自己的面包店", "present": "每天清晨为小镇带来香气", "turning_points": []},
                "needs": [{"name": "safety", "level": 0.4}, {"name": "belonging", "level": 0.7}],
            },
            {
                "id": "char_3", "name": "莉娜", "age": 28, "gender": "女", "pronouns": "她",
                "identity_tags": {"primary": "酒馆老板", "secondary": ["倾听者"], "self_identity": "小镇的耳朵"},
                "personality": {"openness": 0.7, "conscientiousness": 0.6, "extraversion": 0.9, "agreeableness": 0.8, "neuroticism": 0.3},
                "extended_personality": {"empathy": 0.9, "humor": 0.7, "ambition": 0.6, "loyalty": 0.8, "courage": 0.6, "patience": 0.7, "generosity": 0.8},
                "backstory": {"title": "酒馆的灵魂", "childhood": "在酒馆长大", "adulthood": "继承了家族酒馆", "present": "倾听着每一位客人的故事", "turning_points": []},
                "needs": [{"name": "safety", "level": 0.5}, {"name": "belonging", "level": 0.8}],
            },
            {
                "id": "char_4", "name": "托马斯", "age": 55, "gender": "男", "pronouns": "他",
                "identity_tags": {"primary": "镇长", "secondary": ["决策者"], "self_identity": "小镇的守护者"},
                "personality": {"openness": 0.6, "conscientiousness": 0.9, "extraversion": 0.7, "agreeableness": 0.6, "neuroticism": 0.5},
                "extended_personality": {"empathy": 0.5, "humor": 0.4, "ambition": 0.7, "loyalty": 0.9, "courage": 0.8, "patience": 0.6, "generosity": 0.6},
                "backstory": {"title": "负责任的镇长", "childhood": "立志为社区服务", "adulthood": "当选镇长", "present": "管理着小镇的日常事务", "turning_points": []},
                "needs": [{"name": "safety", "level": 0.6}, {"name": "belonging", "level": 0.5}],
            },
            {
                "id": "char_5", "name": "艾米", "age": 23, "gender": "女", "pronouns": "她",
                "identity_tags": {"primary": "见习学者", "secondary": ["冒险者"], "self_identity": "知识的追求者"},
                "personality": {"openness": 0.9, "conscientiousness": 0.5, "extraversion": 0.7, "agreeableness": 0.7, "neuroticism": 0.4},
                "extended_personality": {"empathy": 0.6, "humor": 0.6, "ambition": 0.8, "loyalty": 0.6, "courage": 0.7, "patience": 0.4, "generosity": 0.5},
                "backstory": {"title": "求知的少女", "childhood": "对世界充满好奇", "adulthood": "开始研究历史", "present": "在图书馆学习和探索", "turning_points": []},
                "needs": [{"name": "novelty", "level": 0.8}, {"name": "belonging", "level": 0.4}],
            },
        ]

        result = []
        for i in range(min(num_characters, len(default_chars))):
            char_data = default_chars[i]
            if locations:
                char_data["initial_location"] = locations[i % len(locations)]
            result.append(CharacterConfig(**char_data))
        
        return result

    def _build_character_prompt(self, request: CharacterBatchRequest) -> str:
        location_names = ", ".join(request.locations) if request.locations else "小镇各处"
        return f"""根据以下世界设定，生成 {request.num_characters} 个角色：

【重要】世界设定：{request.world_description}
【重要】时代背景：{request.world_description}

【关键要求】
1. 角色必须完全符合上述世界设定和时代背景
2. 职业、姓名、文化、语言、习俗都必须与时代匹配
3. 例如：如果世界是"大唐盛世的长安"，角色应该是：
   - 商人、书生、官员、宫女、道士、胡商等唐代人物
   - 姓名应该是李白、公孙大娘、安禄山等唐代风格
   - 而不是：图书馆管理员、面包师、酒馆老板（这些是欧洲中世纪风格）

地点：{location_names}

请生成 {request.num_characters} 个角色，每个角色包含：
- id: 唯一标识（如 char_1, char_2）
- name: 姓名（必须符合时代背景）
- age: 年龄
- gender: 性别
- pronouns: 代词
- appearance: 外貌描述（符合时代背景）
- identity_tags: 身份标签（primary主要身份, secondary次要身份, self_identity自我认同）
- social_background: 社会背景（family, education, career, social_network）
- personality: Big Five性格（openness, conscientiousness, extraversion, agreeableness, neuroticism）均为0.0-1.0
- extended_personality: 扩展性格（empathy, humor, ambition, loyalty, courage, patience, generosity）均为0.0-1.0
- backstory: 人物小传（childhood, adolescence, adulthood, present, turning_points）- 必须符合时代背景
- needs: 初始需求队列（如 safety, belonging, novelty 等）
- initial_location: 初始位置

输出JSON格式：
{{
  "characters": [
    {{角色1配置}},
    {{角色2配置}},
    ...
  ]
}}

角色应该多样化，覆盖不同职业、性格、年龄。必须严格符合时代背景！请严格输出JSON。"""

    def _character_system_prompt(self) -> str:
        return """你是一个角色设定生成专家，擅长根据不同的世界设定和时代背景生成符合历史的角色。

【核心原则】
1. 角色职业必须符合时代背景（如大唐盛世应该是：商人、书生、官员、宫女、道士、胡商等）
2. 角色姓名必须符合时代和文化的命名习惯
3. 角色外貌、服饰、习俗必须与时代匹配
4. 绝不能生成与时代不符的现代职业（如图书馆管理员）或欧洲中世纪职业（如面包师、酒馆老板）

请严格按JSON格式输出，characters数组每个元素都要包含完整字段。"""

    def _parse_characters_response(
        self, json_str: str, available_locations: list[str]
    ) -> list[CharacterConfig]:
        """解析云端返回的角色配置（json_str是已经提取的JSON字符串）"""
        try:
            data = json.loads(json_str)
            chars_data = data.get("characters", [])
            logger.info(f"[Worldsmith] 开始解析 {len(chars_data)} 个角色")

            characters = []
            for i, cd in enumerate(chars_data):
                try:
                    # 补充默认字段
                    if "id" not in cd:
                        cd["id"] = f"char_{i+1}"
                    if not cd.get("initial_location") and available_locations:
                        cd["initial_location"] = random.choice(available_locations)

                    # 修复 appearance 字段 - 如果是字符串，转换为字典
                    if isinstance(cd.get("appearance"), str):
                        cd["appearance"] = {"description": cd["appearance"]}
                    elif "appearance" not in cd:
                        cd["appearance"] = {"description": ""}

                    # 修复 identity_tags 字段
                    if "identity_tags" not in cd:
                        cd["identity_tags"] = {}
                    if isinstance(cd["identity_tags"], dict):
                        if "primary" not in cd["identity_tags"]:
                            cd["identity_tags"]["primary"] = "未知"
                        if "secondary" not in cd["identity_tags"]:
                            cd["identity_tags"]["secondary"] = []
                        if isinstance(cd["identity_tags"].get("secondary"), str):
                            cd["identity_tags"]["secondary"] = [cd["identity_tags"]["secondary"]]
                        if "self_identity" not in cd["identity_tags"]:
                            cd["identity_tags"]["self_identity"] = ""
                    else:
                        cd["identity_tags"] = {"primary": str(cd["identity_tags"]), "secondary": [], "self_identity": ""}

                    # 修复 social_background 字段 - 如果是字符串，转换为字典
                    social_bg = cd.get("social_background", {})
                    if isinstance(social_bg, str):
                        social_bg = {"description": social_bg, "family": {}, "education": {}, "career": {}, "social_network": {}}
                    for key in ["family", "education", "career", "social_network"]:
                        if isinstance(social_bg.get(key), str):
                            social_bg[key] = {"description": social_bg[key]}
                        elif not isinstance(social_bg.get(key), dict):
                            social_bg[key] = {}
                    cd["social_background"] = social_bg

                    # 修复 backstory 字段
                    backstory = cd.get("backstory", {})
                    if isinstance(backstory, str):
                        backstory = {"title": "", "childhood": backstory, "adolescence": "", "adulthood": "", "present": "", "turning_points": []}
                    for key in ["title", "childhood", "adolescence", "adulthood", "present"]:
                        if key not in backstory:
                            backstory[key] = ""
                    if "turning_points" not in backstory:
                        backstory["turning_points"] = []
                    
                    # 处理 turning_points 是单个字符串的情况，如 "一个事件描述"
                    turning_points = backstory.get("turning_points")
                    if isinstance(turning_points, str):
                        # 单个字符串转为单个元素的列表
                        backstory["turning_points"] = [{"description": turning_points}]
                    elif isinstance(turning_points, list):
                        # 列表格式，需要确保每个元素是正确的格式
                        fixed_points = []
                        for point in turning_points:
                            if isinstance(point, dict):
                                fixed_points.append(point)
                            elif isinstance(point, str):
                                fixed_points.append({"description": point})
                            else:
                                fixed_points.append({"description": ""})
                        backstory["turning_points"] = fixed_points
                    else:
                        backstory["turning_points"] = []
                    cd["backstory"] = backstory

                    # 修复 needs 字段
                    if isinstance(cd.get("needs"), dict):
                        cd["needs"] = [{"name": k, "level": float(v) if isinstance(v, (int, float)) else 0.5} for k, v in cd["needs"].items()]
                    elif isinstance(cd.get("needs"), list):
                        # 处理 needs 是字符串列表的情况，如 ['belonging', 'safety']
                        fixed_needs = []
                        for item in cd["needs"]:
                            if isinstance(item, dict):
                                fixed_needs.append({"name": item.get("name", "unknown"), "level": float(item.get("level", 0.5))})
                            elif isinstance(item, str):
                                fixed_needs.append({"name": item, "level": 0.5})
                            else:
                                fixed_needs.append({"name": "unknown", "level": 0.5})
                        cd["needs"] = fixed_needs
                    else:
                        cd["needs"] = [{"name": "safety", "level": 0.5}, {"name": "belonging", "level": 0.5}]

                    # 确保 personality 结构完整
                    p = cd.get("personality", {})
                    if not isinstance(p, dict):
                        p = {}
                    cd["personality"] = {
                        "openness": float(p.get("openness", 0.5)),
                        "conscientiousness": float(p.get("conscientiousness", 0.5)),
                        "extraversion": float(p.get("extraversion", 0.5)),
                        "agreeableness": float(p.get("agreeableness", 0.5)),
                        "neuroticism": float(p.get("neuroticism", 0.5)),
                    }

                    # 确保 extended_personality 结构完整
                    ep = cd.get("extended_personality", {})
                    if not isinstance(ep, dict):
                        ep = {}
                    cd["extended_personality"] = {
                        "empathy": float(ep.get("empathy", 0.5)),
                        "humor": float(ep.get("humor", 0.5)),
                        "ambition": float(ep.get("ambition", 0.5)),
                        "loyalty": float(ep.get("loyalty", 0.5)),
                        "courage": float(ep.get("courage", 0.5)),
                        "patience": float(ep.get("patience", 0.5)),
                        "generosity": float(ep.get("generosity", 0.5)),
                    }

                    characters.append(CharacterConfig(**cd))
                    logger.info(f"[Worldsmith] 角色解析成功 [{i}]: {cd.get('name', 'unknown')}")
                except Exception as e:
                    logger.warning(f"[Worldsmith] 角色解析失败 [{i}]: {e}, 数据: {str(cd)[:200]}")
            
            logger.info(f"[Worldsmith] 角色解析完成，成功 {len(characters)} 个，失败 {len(chars_data) - len(characters)} 个")
            return characters

        except Exception as e:
            logger.error(f"[Worldsmith] 角色响应解析失败: {e}")
            logger.error(f"[Worldsmith] JSON字符串长度: {len(json_str)}")
            return []

    async def _generate_introduce_texts(
        self, characters: list[CharacterConfig]
    ) -> list[CharacterConfig]:
        """本地 Qwen 为每个角色生成第一人称自我介绍"""
        for char in characters:
            try:
                prompt = f"""请为以下角色生成一段简短的"第一人称"自我介绍文本，用于UI卡片展示。

角色姓名：{char.name}
年龄：{char.age}
性别：{char.gender}
主要身份：{char.identity_tags.primary}
自我认同：{char.identity_tags.self_identity}
性格特点：Big Five: O={char.personality.openness}, C={char.personality.conscientiousness}, E={char.personality.extraversion}, A={char.personality.agreeableness}, N={char.personality.neuroticism}

要求：
- 50-100字左右
- 第一人称"我"来介绍自己
- 体现性格特点
- 不要提及年龄数字
- 自然、亲切

直接输出自我介绍文本，不要其他内容。"""

                response = await self._local.chat(
                    messages=[{"role": "user", "content": prompt}],
                    system="你是一个角色助手。",
                    temperature=0.2,
                    max_tokens=150,
                )

                char.introduce_text = response.strip()
                self._metrics.local_call_count += 1

            except Exception as e:
                logger.warning(f"[Worldsmith] introduce_text 生成失败 [{char.name}]: {e}")
                char.introduce_text = f"我是{char.name}，{char.identity_tags.primary}。"

        return characters

    async def _fill_missing_appearances(
        self, characters: list[CharacterConfig]
    ) -> list[CharacterConfig]:
        """为缺少 appearance 信息的角色补充生成外貌描述"""
        for char in characters:
            # 检查 appearance 是否为空或不完整
            appearance = char.appearance
            needs_fill = False

            if not appearance:
                needs_fill = True
            elif isinstance(appearance, dict):
                # 检查所有字段是否为空
                if not any(appearance.get(field) for field in ['height', 'build', 'hair', 'eyes', 'face', 'distinguishing_features']):
                    needs_fill = True
            elif isinstance(appearance, str) and not appearance.strip():
                needs_fill = True

            if not needs_fill:
                continue

            try:
                prompt = f"""为以下角色生成外貌描述：

角色姓名：{char.name}
年龄：{char.age}
性别：{char.gender}
职业：{char.identity_tags.primary}
时代背景：{char.identity_tags.get('description', '文艺复兴时期')}

请生成JSON格式的外貌信息：
{{
  "height": "身高描述（如：高挑、中等、矮小）",
  "build": "体型描述（如：健壮、苗条、丰满）",
  "hair": "发型发色描述",
  "eyes": "眼神描述",
  "face": "面部特征描述",
  "distinguishing_features": ["特征1", "特征2"]
}}

只输出JSON，不要其他内容。"""

                response = await self._local.chat(
                    messages=[{"role": "user", "content": prompt}],
                    system="你是一个角色设定助手。",
                    temperature=0.3,
                    max_tokens=300,
                )

                json_str = self._extract_json(response)
                data = json.loads(json_str)

                # 更新 appearance
                char.appearance = data
                self._metrics.local_call_count += 1
                logger.info(f"[Worldsmith] 为角色 [{char.name}] 补充生成 appearance")

            except Exception as e:
                logger.warning(f"[Worldsmith] appearance 生成失败 [{char.name}]: {e}")
                # 使用默认空结构
                char.appearance = {
                    "height": "",
                    "build": "",
                    "hair": "",
                    "eyes": "",
                    "face": "",
                    "distinguishing_features": []
                }

        return characters

    async def get_complementary_tips(
        self, characters: list[CharacterConfig]
    ) -> list[dict]:
        """本地 Qwen 提供性格互补/冲突提示（不作为最终决策）"""
        if len(characters) < 2:
            return []

        prompt = f"""分析以下角色之间的性格互补和冲突：

{chr(10).join([f"- {c.name}: {c.identity_tags.primary}" for c in characters])}

请输出JSON：
{{
  "tips": [
    {{
      "from": "角色A",
      "to": "角色B",
      "type": "互补|冲突|中性",
      "reason": "原因说明"
    }}
  ]
}}

只分析相邻角色对。只输出JSON。"""

        try:
            response = await self._local.chat(
                messages=[{"role": "user", "content": prompt}],
                system="你是一个社交分析助手。",
                temperature=0.2,
                max_tokens=500,
            )

            # 使用专门的 tips 提取逻辑
            json_str = self._extract_tips_json(response)
            data = json.loads(json_str)
            self._metrics.local_call_count += 1
            return data.get("tips", [])

        except Exception as e:
            logger.warning(f"[Worldsmith] 性格提示生成失败: {e}")
            return []

    def _extract_tips_json(self, text: str) -> str:
        """专门提取 tips JSON，处理被污染的响应"""
        import json

        # 清理 [THINK] 和 [SPEAK] 标签
        text = re.sub(r'\[THINK\].*?\[/THINK\]', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'\[/?SPEAK\]', '', text, flags=re.IGNORECASE)
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)

        # 查找 {"tips": [ 模式
        match = re.search(r'\{\s*"tips"\s*:\s*\[', text)
        if not match:
            raise ValueError("找不到 tips JSON")

        # 从 "tips" 的 " 位置开始
        start = match.start()

        # 使用栈式匹配找到 ] 和 }
        depth_brace = 0  # { }
        depth_bracket = 0  # [ ]
        in_string = False
        escape_next = False

        for i in range(start, len(text)):
            char = text[i]

            if escape_next:
                escape_next = False
                continue

            if char == '\\' and in_string:
                escape_next = True
                continue

            if char == '"':
                in_string = not in_string
                continue

            if in_string:
                continue

            if char == '{':
                depth_brace += 1
            elif char == '}':
                depth_brace -= 1
                if depth_brace == 0 and depth_bracket == 0:
                    # 找到了完整的 {"tips": [...]} 对象
                    json_str = text[start:i+1]
                    try:
                        json.loads(json_str)
                        return json_str
                    except:
                        pass
            elif char == '[':
                depth_bracket += 1
            elif char == ']':
                depth_bracket -= 1

        # 如果栈式匹配失败，尝试 fallback
        logger.warning(f"[Worldsmith] tips 栈式匹配失败，使用 fallback")
        return self._extract_json(text, expected_keys=["tips"])

    # =============================================================================
    # 关系编织 (云端 + 本地)
    # =============================================================================

    async def generate_relationships(
        self, characters: list[CharacterConfig]
    ) -> list[CharacterPairRelationship]:
        """
        调用云端 MiniMax 生成每对角色的 shared_history
        本地 Qwen 检查视角扭曲
        """
        logger.info(f"[Worldsmith] 生成 {len(characters)} 个角色的关系")

        if len(characters) < 2:
            return []

        relationships = []

        # 生成所有两两组合
        for i in range(len(characters)):
            for j in range(i + 1, len(characters)):
                char_a = characters[i]
                char_b = characters[j]

                rel = await self._generate_pair_relationship(char_a, char_b)
                if rel:
                    relationships.append(rel)

        # 本地 Qwen 检查视角扭曲
        validations = await self._validate_shared_histories(relationships, characters)

        # 标记有问题的关系
        for validation in validations:
            for rel in relationships:
                if rel.from_id == validation.from_id and rel.to_id == validation.to_id:
                    if validation.perspective_distortion_detected:
                        rel.potential_conflicts.append("视角可能存在扭曲")

        logger.info(f"[Worldsmith] 关系生成完成: {len(relationships)} 条")
        return relationships

    async def _generate_pair_relationship(
        self, char_a: CharacterConfig, char_b: CharacterConfig
    ) -> Optional[CharacterPairRelationship]:
        """为一对角色生成关系和 shared_history"""
        prompt = f"""为以下两个角色生成他们的关系和共同历史：

角色A - {char_a.name}（{char_a.identity_tags.primary}）
角色B - {char_b.name}（{char_b.identity_tags.primary}）

请生成（JSON格式，shared_history限制在150字以内）：
{{
  "from_id": "{char_a.id}",
  "to_id": "{char_b.id}",
  "relationship_type": "关系类型",
  "strength": 0.5,
  "shared_history": "50-100字的共同历史..."
}}

只输出JSON，不要其他内容。"""

        try:
            response = await self._cloud.chat(
                messages=[{"role": "user", "content": prompt}],
                system="你是一个关系设定专家。请严格按JSON格式输出。",
                temperature=0.7,
                max_tokens=2000,
            )

            json_str = self._extract_json(response)
            data = json.loads(json_str)

            return CharacterPairRelationship(
                from_id=data.get("from_id", char_a.id),
                to_id=data.get("to_id", char_b.id),
                relationship_type=data.get("relationship_type", "stranger"),
                strength=data.get("strength", 0.0),
                shared_history=data.get("shared_history", ""),
            )

        except Exception as e:
            logger.error(f"[Worldsmith] 关系生成失败 [{char_a.name}-{char_b.name}]: {e}")
            return CharacterPairRelationship(
                from_id=char_a.id,
                to_id=char_b.id,
                relationship_type="stranger",
                strength=0.0,
            )

    async def _validate_shared_histories(
        self,
        relationships: list[CharacterPairRelationship],
        characters: list[CharacterConfig],
    ) -> list[SharedHistoryValidation]:
        """本地 Qwen 检查 shared_history 是否包含对另一方的视角扭曲"""
        validations = []

        for rel in relationships:
            char_a = next((c for c in characters if c.id == rel.from_id), None)
            char_b = next((c for c in characters if c.id == rel.to_id), None)

            if not char_a or not char_b:
                continue

            prompt = f"""检查以下 shared_history 是否存在视角扭曲：

视角人物A：{char_a.name}（{char_a.identity_tags.primary}）
视角人物B：{char_b.name}（{char_b.identity_tags.primary}）

shared_history 内容：
{rel.shared_history}

请检查：
1. 是否只描述了A的视角而忽略B的感受/想法？
2. 是否有明显偏袒某一方的情况？
3. 是否有不符合各自性格的反应？

输出JSON：
{{
  "from_id": "{rel.from_id}",
  "to_id": "{rel.to_id}",
  "is_valid": true/false,
  "issues": ["问题1", "问题2"],
  "perspective_distortion_detected": true/false
}}

只输出JSON。"""

            try:
                response = await self._local.chat(
                    messages=[{"role": "user", "content": prompt}],
                    system="你是一个叙事一致性检查专家。",
                    temperature=0.1,
                    max_tokens=200,
                )

                json_str = self._extract_json(response)
                data = json.loads(json_str)
                validations.append(SharedHistoryValidation(**data))
                self._metrics.local_call_count += 1

            except Exception as e:
                logger.warning(f"[Worldsmith] 视角校验失败 [{rel.from_id}]: {e}")

        return validations

    # =============================================================================
    # 完整世界工坊流程
    # =============================================================================

    async def generate_full_world(
        self, request: WorldsmithGenerateRequest
    ) -> dict:
        """
        完整流程：
        1. 生成世界骨架（云端）
        2. 生成角色（云端 + 本地 introduce_text）
        3. 编织关系（云端 + 本地视角校验）
        """
        logger.info(f"[Worldsmith] 完整世界生成: {request.description[:50]}...")

        # 1. 世界骨架
        world = await self.generate_world(request.description)
        location_names = [loc.name for loc in world.locations]

        # 2. 角色批量生成（如果失败会抛出 ValueError）
        batch_req = CharacterBatchRequest(
            world_description=request.description,
            locations=location_names,
            num_characters=request.num_characters,
        )
        characters = await self.generate_characters(batch_req)

        # 2.5 补充缺失的 appearance 信息（使用本地模型）
        characters = await self._fill_missing_appearances(characters)

        # 3. 关系编织
        relationships = await self.generate_relationships(characters)

        # 4. 性格互补提示
        tips = await self.get_complementary_tips(characters)

        return {
            "world": world,
            "characters": characters,
            "relationships": relationships,
            "personality_tips": tips,
            "metrics": self._metrics,
        }

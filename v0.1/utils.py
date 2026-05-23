"""
utils.py — 公共工具函数
"""

import yaml
import logging
from pathlib import Path
from typing import Union

from agent import CharacterConfig, CoreInstinct

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


def load_character(path: Union[str, Path] = "character.yaml") -> CharacterConfig:
    """
    从 YAML 文件加载角色配置
    
    参数:
        path: 配置文件路径
    
    返回:
        CharacterConfig 对象
    
    异常:
        FileNotFoundError: 文件不存在
        ValueError: 配置缺少必需字段
    """
    path = Path(path)
    
    if not path.exists():
        error_msg = f"角色配置文件不存在: {path}"
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)
    
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    
    # 配置验证
    required_fields = ["basic_info", "psychology", "desire_initial", "core_instincts"]
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        error_msg = f"配置文件缺少必需字段: {', '.join(missing_fields)}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    logger.info(f"成功加载角色配置: {data['basic_info'].get('name', '未知')}")
    
    return CharacterConfig(
        id=data["basic_info"]["id"],
        name=data["basic_info"]["name"],
        age=data["basic_info"]["age"],
        gender=data["basic_info"]["gender"],
        pronouns=data["basic_info"]["pronouns"],
        identity_tags=data["basic_info"]["identity_tags"],
        personality=data["psychology"]["personality"]["big_five"],
        personality_extended=data["psychology"]["personality"].get("extended"),
        desire_initial=data["desire_initial"],
        core_instincts=[CoreInstinct.parse_obj(i) for i in data["core_instincts"]["ABSOLUTE_PRIORITY"]],
        emergence_config=data.get("emergence_config", {}),
        backstory=data.get("backstory", ""),
    )
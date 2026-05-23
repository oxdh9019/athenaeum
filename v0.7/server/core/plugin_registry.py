"""
plugin_registry.py — V0.7 插件注册中心
支持装饰器和显式注册双轨制
"""

import logging
from typing import Dict, Type, Optional, Any
from .interfaces import ILLMClient, IModelRouter

logger = logging.getLogger(__name__)


class PluginRegistry:
    """
    插件注册中心
    管理 LLM 客户端、路由器等插件的注册和获取
    """

    _llm_clients: Dict[str, Type[ILLMClient]] = {}
    _llm_instances: Dict[str, ILLMClient] = {}
    _routers: Dict[str, IModelRouter] = {}
    _default_router: Optional[IModelRouter] = None

    @classmethod
    def register_llm_client(cls, name: str, client_class: Type[ILLMClient]):
        """
        显式注册 LLM 客户端

        Args:
            name: 客户端名称 ("local", "cloud")
            client_class: 客户端类
        """
        if name in cls._llm_clients:
            logger.warning(f"[Registry] LLM client '{name}' 已注册，将被覆盖")
        cls._llm_clients[name] = client_class
        logger.info(f"[Registry] LLM 客户端已注册: {name} -> {client_class.__name__}")

    @classmethod
    def get_llm_client(cls, name: str) -> Optional[ILLMClient]:
        """
        获取 LLM 客户端实例（单例模式）

        Args:
            name: 客户端名称

        Returns:
            ILLMClient 实例或 None
        """
        if name not in cls._llm_clients:
            logger.error(f"[Registry] LLM 客户端 '{name}' 未注册")
            return None

        if name not in cls._llm_instances:
            cls._llm_instances[name] = cls._llm_clients[name]()
            logger.info(f"[Registry] LLM 客户端实例化: {name}")

        return cls._llm_instances[name]

    @classmethod
    def list_llm_clients(cls) -> list[str]:
        """列出所有已注册的客户端名称"""
        return list(cls._llm_clients.keys())

    @classmethod
    def register_router(cls, name: str, router: IModelRouter):
        """
        注册路由器

        Args:
            name: 路由器名称
            router: 路由器实例
        """
        cls._routers[name] = router
        if cls._default_router is None:
            cls._default_router = router
        logger.info(f"[Registry] 路由器已注册: {name}")

    @classmethod
    def get_router(cls, name: str = "default") -> Optional[IModelRouter]:
        """获取路由器实例"""
        if name == "default":
            return cls._default_router
        return cls._routers.get(name)

    @classmethod
    def set_default_router(cls, router: IModelRouter):
        """设置默认路由器"""
        cls._default_router = router


def register_llm_client(name: str):
    """
    装饰器：注册 LLM 客户端

    用法：
        @register_llm_client("local")
        class LocalOllamaClient(ILLMClient):
            ...
    """
    def deco(cls: Type[ILLMClient]):
        PluginRegistry.register_llm_client(name, cls)
        return cls
    return deco


def register_router(name: str = "default"):
    """
    装饰器：注册路由器

    用法：
        @register_router("default")
        class DefaultRouter(IModelRouter):
            ...
    """
    def deco(cls: Type[IModelRouter]):
        # 先实例化，再注册
        instance = cls()
        PluginRegistry.register_router(name, instance)
        return cls
    return deco
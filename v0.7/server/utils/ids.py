"""
ids.py — V0.7 统一短 ID 生成

【为什么不用 `str(uuid.uuid4())[:8]`？】
UUID4 前 8 字符只有 32 bit 熵，~43 亿次就有 50% 冲突概率；
对会话 ID 这种需要保持唯一性的场景不够。改用 `secrets.token_hex(6)`：
48 bit 熵、URL/日志安全、实现简单。
"""
import secrets


def short_id(prefix: str = "") -> str:
    """
    生成 12 字符（6 字节）的 URL/日志安全随机 ID。
    可选 prefix（如 'sess_'）便于在日志里一眼区分。
    """
    return f"{prefix}{secrets.token_hex(6)}"

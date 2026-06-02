"""
llm_parsing.py — V0.7 统一的 LLM 输出解析与 prompt 注入防护

背景：
- LLM 输出 JSON 经常带 markdown fence、前后自然语言、尾随逗号等
- 项目里 7 处用不同 regex 解析，有的用 `[^}]+`（嵌套对象直接截断）
- 用户输入拼进 prompt 可能携带指令注入（"忽略之前所有指令..."）

本模块提供两个工具：
- parse_llm_json(text): 从 LLM 输出中提取并解析 JSON 对象
- inject_guard(text, max_length, purpose): 对拼入 prompt 的用户/历史文本做清洗+截断
"""
import json
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


# 抓取 markdown 围栏 ```json ... ``` 里的内容（qwen3.5/gpt 都常用）
_FENCE_RE = re.compile(r"```(?:json|JSON)?\s*(\{.*?\})\s*```", re.DOTALL)
# 抓取最外层 { ... } 块（用栈扫描，能正确处理嵌套）
_OUTER_OBJ_RE = re.compile(r"\{.*\}", re.DOTALL)
# 抓取最外层 [ ... ] 块
_OUTER_ARR_RE = re.compile(r"\[.*\]", re.DOTALL)


def _strip_trailing_commas(s: str) -> str:
    """
    修复 JSON 尾随逗号 ",}" -> "}", ",]" -> "]"。
    只去掉对象/数组的尾随逗号，不动字符串里的逗号。
    """
    return re.sub(r",(\s*[}\]])", r"\1", s)


def _extract_json_block(text: str) -> Optional[str]:
    """
    从 LLM 输出中提取 JSON 字符串片段（不做解析，只切片）。
    优先级：markdown fence > 第一个 { 到匹配的 } > 第一个 [ 到匹配的 ]
    """
    if not text:
        return None
    text = text.strip()

    # 1. markdown fence ```json ... ```
    m = _FENCE_RE.search(text)
    if m:
        return m.group(1).strip()

    # 2. 找最外层 {...}（栈扫描，处理嵌套）
    obj = _find_balanced(text, "{", "}")
    if obj is not None:
        return obj

    # 3. 找最外层 [...]（栈扫描，处理嵌套）
    arr = _find_balanced(text, "[", "]")
    if arr is not None:
        return arr

    return None


def _find_balanced(text: str, open_ch: str, close_ch: str) -> Optional[str]:
    """
    在 text 中找第一个 open_ch 到其对应 close_ch 的子串（栈扫描，正确处理嵌套）。
    字符串字面量内的开闭括号忽略。
    """
    start = text.find(open_ch)
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape_next = False
    for i in range(start, len(text)):
        ch = text[i]

        if escape_next:
            escape_next = False
            continue
        if in_string:
            if ch == "\\":
                escape_next = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
        elif ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return text[start:i + 1]

    return None


def parse_llm_json(text: str, *, default: Optional[dict] = None) -> Optional[dict]:
    """
    从 LLM 输出中提取并解析 JSON 对象。

    Args:
        text: LLM 原始输出（可能含 markdown fence、前后自然语言、尾随逗号）
        default: 解析失败时返回的默认值（默认 None）

    Returns:
        解析成功返回 dict，失败返回 default。

    处理流程：
        1. 提取 markdown fence ```json ... ``` 内的 JSON
        2. 否则用栈扫描找最外层 {...} 或 [...]
        3. 去掉尾随逗号
        4. json.loads
        5. 失败时回退：尝试整个 text 直接 json.loads
    """
    if not text:
        return default

    # 先尝试整段直接解析（LLM 偶尔输出纯 JSON 无 fence）
    try:
        return json.loads(text.strip())
    except (json.JSONDecodeError, ValueError):
        pass

    block = _extract_json_block(text)
    if block is None:
        logger.debug(f"[parse_llm_json] 未找到 JSON 块: {text[:80]!r}...")
        return default

    # 第一次尝试
    try:
        return json.loads(block)
    except json.JSONDecodeError:
        pass

    # 修复尾随逗号后重试
    fixed = _strip_trailing_commas(block)
    if fixed != block:
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            pass

    logger.debug(f"[parse_llm_json] JSON 解析失败: {block[:80]!r}...")
    return default


# 用于清洗用户输入的最长长度（防止巨型 prompt + 防止注入面过大）
DEFAULT_MAX_INPUT_LENGTH = 2000


def inject_guard(
    text: str,
    *,
    max_length: int = DEFAULT_MAX_INPUT_LENGTH,
    purpose: str = "user_input",
) -> str:
    """
    清洗拼进 prompt 的文本，防 prompt 注入。

    Args:
        text: 用户输入或历史对话文本
        max_length: 截断阈值（字符数，非字节数）
        purpose: 调用方标签，仅用于日志

    处理：
        1. 截断到 max_length
        2. 把可能让 LLM 误判为 prompt 分隔符的序列替换/转义
           - 三引号 \"\"\" 替换为三个单引号
           - 反引号 ``` 替换为空格
           - 显式指令前缀如 "忽略", "ignore", "system:" 做截断处理
        3. 不修改语义内容（中文/英文标点不动）

    Returns:
        清洗后的字符串
    """
    if not text:
        return ""

    if len(text) > max_length:
        logger.info(f"[inject_guard:{purpose}] 文本超长 ({len(text)} > {max_length})，截断")
        text = text[:max_length] + "...(已截断)"

    # 把可能混淆 prompt 结构的 markdown 围栏转义
    # 用全角反引号 ｀ 替代半角 `
    text = text.replace("```", "｀｀｀")
    text = text.replace("`", "｀")

    # 三引号（多行字符串分隔符）替换
    text = text.replace('"""', "'''")

    return text

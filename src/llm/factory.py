"""LLM Provider 工厂 — 根据 config.llm.provider 返回对应实现。"""

import logging

from ..config import LLMConfig
from .base import BaseLLM
from .deepseek_llm import DeepSeekLLM
from .openai_llm import OpenAILLM

logger = logging.getLogger(__name__)


def get_llm(config: LLMConfig) -> BaseLLM:
    """根据 LLMConfig.provider 返回对应的 LLM 实例。"""
    provider = config.provider.lower()
    logger.info("正在初始化 LLM provider: %s", provider)

    if provider == "deepseek":
        return DeepSeekLLM(config)
    elif provider == "openai":
        return OpenAILLM(config)
    elif provider == "anthropic":
        raise NotImplementedError("Anthropic Claude provider 尚未实现。请使用 deepseek 或 openai。")
    else:
        raise ValueError(
            f"未知的 LLM provider: '{config.provider}'。支持: deepseek, openai, anthropic (预留)"
        )

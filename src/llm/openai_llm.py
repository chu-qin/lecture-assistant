"""OpenAI 原生 API LLM 实现。"""

import logging
import time
from collections.abc import Iterator

from openai import OpenAI

from ..config import LLMConfig
from .base import (
    AuthenticationError,
    BaseLLM,
    LLMError,
    LLMResponse,
    LLMTimeoutError,
    RateLimitError,
)

logger = logging.getLogger(__name__)


class OpenAILLM(BaseLLM):
    def __init__(self, config: LLMConfig):
        if not config.openai_api_key:
            raise AuthenticationError(
                "OpenAI API Key 未设置。\n"
                "请在 config.yaml 中设置 openai_api_key 或设置环境变量 OPENAI_API_KEY"
            )
        self._config = config
        self._client = OpenAI(
            api_key=config.openai_api_key,
            base_url=config.base_url,
            timeout=float(config.timeout),
        )
        logger.info("OpenAILLM 初始化完成，model=%s", config.model)

    def chat(self, messages: list[dict[str, str]], **kwargs) -> LLMResponse:
        model = kwargs.pop("model", self._config.model)
        temperature = kwargs.pop("temperature", self._config.temperature)
        max_tokens = kwargs.pop("max_tokens", self._config.max_tokens)

        last_error = None
        for attempt in range(self._config.max_retries):
            try:
                api_params = dict(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    **kwargs,
                )
                if max_tokens is not None:
                    api_params["max_tokens"] = max_tokens
                response = self._client.chat.completions.create(**api_params)
                choice = response.choices[0]
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0,
                }
                return LLMResponse(
                    content=choice.message.content or "",
                    model=response.model,
                    usage=usage,
                    finish_reason=choice.finish_reason or "stop",
                )
            except Exception as e:
                last_error = e
                logger.warning(
                    "API 调用失败 (尝试 %d/%d): %s",
                    attempt + 1,
                    self._config.max_retries,
                    e,
                )
                if attempt < self._config.max_retries - 1:
                    time.sleep(2**attempt)

        return self._handle_error(last_error)

    def stream_chat(self, messages: list[dict[str, str]], **kwargs) -> Iterator[str]:
        model = kwargs.pop("model", self._config.model)
        temperature = kwargs.pop("temperature", self._config.temperature)
        max_tokens = kwargs.pop("max_tokens", self._config.max_tokens)

        last_error = None
        for attempt in range(self._config.max_retries):
            try:
                api_params = dict(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    stream=True,
                    **kwargs,
                )
                if max_tokens is not None:
                    api_params["max_tokens"] = max_tokens
                stream = self._client.chat.completions.create(**api_params)
                for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
                return
            except Exception as e:
                last_error = e
                logger.warning(
                    "流式 API 调用失败 (尝试 %d/%d): %s",
                    attempt + 1,
                    self._config.max_retries,
                    e,
                )
                if attempt < self._config.max_retries - 1:
                    time.sleep(2**attempt)

        yield f"\n[错误] {self._handle_error(last_error)}"

    @staticmethod
    def _handle_error(error: Exception | None) -> LLMResponse:
        if error is None:
            return LLMResponse(content="", model="unknown", usage={})
        msg = str(error)
        if "authentication" in msg.lower() or "401" in msg:
            raise AuthenticationError(f"API Key 无效: {msg}")
        if "rate" in msg.lower() or "429" in msg:
            raise RateLimitError(f"API 速率限制: {msg}")
        if "timeout" in msg.lower():
            raise LLMTimeoutError(f"API 请求超时: {msg}")
        raise LLMError(f"API 调用失败: {msg}")

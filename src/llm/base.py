"""LLM 抽象基类与数据契约。"""

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass

# ============================================================
# 异常
# ============================================================


class LLMError(Exception):
    """LLM 模块基础异常。"""

    pass


class AuthenticationError(LLMError):
    """API 密钥无效。"""

    pass


class RateLimitError(LLMError):
    """API 速率限制。"""

    pass


class LLMTimeoutError(LLMError):
    """API 请求超时。"""

    pass


class PromptNotFoundError(LLMError):
    """提示词模板文件不存在。"""

    pass


# ============================================================
# 数据类
# ============================================================


@dataclass
class LLMResponse:
    content: str
    model: str
    usage: dict[str, int]  # {"prompt_tokens": N, "completion_tokens": M, "total_tokens": T}
    finish_reason: str = "stop"


# ============================================================
# 抽象基类
# ============================================================


class BaseLLM(ABC):
    @abstractmethod
    def chat(self, messages: list[dict[str, str]], **kwargs) -> LLMResponse:
        """发送对话请求，返回完整回复。"""
        ...

    @abstractmethod
    def stream_chat(self, messages: list[dict[str, str]], **kwargs) -> Iterator[str]:
        """流式对话，逐 token 产出文本片段。"""
        ...

    def load_prompt(self, prompt_name: str, **variables) -> str:
        """从 prompts/<lang>/ 目录加载提示词模板并填充变量。"""
        from ..config import get_project_root

        prompt_dir = get_project_root() / "prompts"

        # 根据当前语言选择子目录，CLI 环境默认 zh
        try:
            from src.i18n import get_language

            lang = get_language()
        except Exception:
            lang = "zh"

        prompt_path = prompt_dir / lang / prompt_name
        if not prompt_path.exists():
            prompt_path = prompt_dir / "zh" / prompt_name

        if not prompt_path.exists():
            raise PromptNotFoundError(
                f"Prompt template not found: {prompt_path}"
            )

        template = prompt_path.read_text(encoding="utf-8")
        return template.format(**variables)

"""ASR 抽象基类与数据契约。"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

# ============================================================
# 异常
# ============================================================


class ASRError(Exception):
    """ASR 模块基础异常。"""

    pass


class ASRModelLoadError(ASRError):
    """模型加载失败。"""

    pass


class ASRInferenceError(ASRError):
    """推理过程出错。"""

    pass


# ============================================================
# 数据类
# ============================================================


@dataclass
class ASRSegment:
    text: str
    start: float = 0.0
    end: float = 0.0
    confidence: float = 1.0


@dataclass
class ASRResult:
    full_text: str
    segments: list[ASRSegment] = field(default_factory=list)
    language: str = "zh"
    duration_seconds: float = 0.0
    metadata: dict[str, str] = field(default_factory=dict)


# ============================================================
# 抽象基类
# ============================================================


class BaseASR(ABC):
    @abstractmethod
    def transcribe(self, audio_path: Path) -> ASRResult:
        """将音频文件转为文本。"""
        ...

    @abstractmethod
    def save_transcript(self, result: ASRResult, output_path: Path) -> Path:
        """将转录结果保存到文件。"""
        ...

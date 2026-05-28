"""FunASR SenseVoiceSmall 语音识别实现。"""

import json
import logging
import re
from pathlib import Path

import streamlit as st

from ..config import ASRConfig
from .base import (
    ASRInferenceError,
    ASRModelLoadError,
    ASRResult,
    ASRSegment,
    BaseASR,
)


@st.cache_resource
def get_asr_model(config: ASRConfig) -> "FunASRSenseVoiceASR":
    """缓存 ASR 模型实例，避免重复加载 ~900MB 模型文件。"""
    return FunASRSenseVoiceASR(config)


logger = logging.getLogger(__name__)


def _format_timestamp(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"[{h:02d}:{m:02d}:{s:06.3f}]"


def _clean_sensevoice_text(raw_text: str) -> str:
    """清理 SenseVoice 输出的特殊标记。

    SenseVoice 输出示例:
        <|zh|><|NEUTRAL|><|Speech|><|withitn|>实际文本内容
    或者输出包含大量特殊记号如:
        < | zh | > < | NEUTRAL | > < | S pe ech | > < | withi tn | >实际文本

    需要把特殊标记和空格去掉，只保留中文文本内容。
    """
    if not raw_text:
        return ""

    # 去掉所有 <| 和 |> 包裹的特殊 token（粘合写法）
    text = re.sub(r"<\s*\|\s*[^|>]*\s*\|\s*>", " ", raw_text)

    # 去掉空的特殊标记残留
    text = re.sub(r"<\s*\|\s*>", " ", text)

    # 合并多余空格
    text = re.sub(r"\s{2,}", " ", text)

    # 去掉行首行尾的空白和多余符号
    text = text.strip(",，。. \t\n")

    return text


class FunASRSenseVoiceASR(BaseASR):
    def __init__(self, config: ASRConfig):
        self._config = config
        self._model = None
        self._loaded = False
        self._load_model()

    def _load_model(self):
        logger.info("加载 FunASR 模型: %s (device=%s)", self._config.model, self._config.device)
        try:
            from funasr import AutoModel

            device = self._config.device
            if device == "cuda":
                try:
                    import torch

                    if not torch.cuda.is_available():
                        logger.warning("CUDA 不可用，降级为 CPU")
                        device = "cpu"
                except ImportError:
                    device = "cpu"

            # 清理旧的锁文件
            import os

            lock_dir = os.path.join(
                os.environ.get("MODELSCOPE_CACHE", ""),
                ".lock",
            )
            if os.path.isdir(lock_dir):
                for root, dirs, files in os.walk(lock_dir):
                    for f in files:
                        if f.endswith(".lock"):
                            lp = os.path.join(root, f)
                            try:
                                os.remove(lp)
                            except Exception:
                                pass

            self._model = AutoModel(
                model=self._config.model,
                vad_model="fsmn-vad",
                punc_model="ct-punc",
                device=device,
            )
            self._loaded = True
            logger.info("FunASR 模型加载完成")
        except Exception as e:
            raise ASRModelLoadError(f"FunASR 模型加载失败: {e}")

    def transcribe(self, audio_path: Path) -> ASRResult:
        if not self._loaded or self._model is None:
            raise ASRModelLoadError("模型未加载")

        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")

        logger.info("开始转录: %s", audio_path.name)
        try:
            result = self._model.generate(
                input=str(audio_path),
                language=self._config.language,
                use_itn=True,
                batch_size_s=self._config.batch_size * 60,
            )
        except Exception as e:
            raise ASRInferenceError(f"转录失败: {e}")

        if not result or len(result) == 0:
            logger.warning("转录结果为空")
            return ASRResult(full_text="", language=self._config.language)

        return self._parse_result(result, audio_path)

    def _parse_result(self, result: list[dict], audio_path: Path) -> ASRResult:
        """解析 FunASR 返回结果，清理特殊 token。"""
        segments: list[ASRSegment] = []
        full_texts: list[str] = []

        for item in result:
            raw_text = item.get("text", "").strip()
            if not raw_text:
                continue

            # 清理 SenseVoice 的特殊标记
            clean_text = _clean_sensevoice_text(raw_text)
            if not clean_text:
                continue

            timestamp = item.get("timestamp", [])

            # FunASR 返回的时间戳可能是 [[[start_ms, end_ms], ...], ...]
            start = 0.0
            end = 0.0
            if timestamp and self._config.use_timestamps:
                try:
                    # 尝试解析嵌套的 timestamp 结构
                    ts_data = timestamp
                    # 可能有多层嵌套: [[[s1,e1],[s2,e2]], ...]
                    if isinstance(ts_data, list) and len(ts_data) > 0:
                        # 提取所有时间点
                        flat_ts = []

                        def _flatten(lst):
                            for elem in lst:
                                if isinstance(elem, list) and len(elem) > 0:
                                    if isinstance(elem[0], (int, float)):
                                        flat_ts.append(elem)
                                    else:
                                        _flatten(elem)

                        _flatten(ts_data)

                        if flat_ts:
                            # 取第一段的开始和最后一段的结束
                            start = float(flat_ts[0][0]) / 1000.0
                            end = float(flat_ts[-1][1]) / 1000.0
                except (IndexError, TypeError, ValueError):
                    pass

            segments.append(ASRSegment(text=clean_text, start=start, end=end))
            full_texts.append(clean_text)

        full_text = "\n".join(full_texts)
        duration = max((s.end for s in segments), default=0.0)

        # 如果没有有效的时间戳，用估算时长
        if duration == 0.0 and segments:
            logger.info("未提取到有效时间戳，时长设为 0")

        return ASRResult(
            full_text=full_text,
            segments=segments,
            language=self._config.language,
            duration_seconds=duration,
            metadata={
                "source_file": str(audio_path.name),
                "model": self._config.model,
            },
        )

    def save_transcript(self, result: ASRResult, output_path: Path) -> Path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        lines: list[str] = []
        for seg in result.segments:
            if self._config.use_timestamps and seg.start > 0:
                ts = _format_timestamp(seg.start)
                lines.append(f"{ts} {seg.text}")
            else:
                lines.append(seg.text)

        txt_content = "\n".join(lines)
        output_path.write_text(txt_content, encoding="utf-8-sig")
        logger.info("转录文本已保存: %s", output_path)

        json_path = output_path.with_suffix(".json")
        json_data = {
            "full_text": result.full_text,
            "language": result.language,
            "duration_seconds": result.duration_seconds,
            "segments": [
                {"text": s.text, "start": s.start, "end": s.end, "confidence": s.confidence}
                for s in result.segments
            ],
            "metadata": result.metadata,
        }
        json_path.write_text(json.dumps(json_data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("转录 JSON 已保存: %s", json_path)

        return output_path

    @property
    def model_loaded(self) -> bool:
        return self._loaded

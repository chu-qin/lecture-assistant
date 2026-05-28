"""
课堂助手 - 配置模块。
所有模型缓存、外部工具路径均强制指向项目内部，
确保删除项目目录即彻底卸载，不在系统其他位置残留任何文件。
"""

import os

from dotenv import load_dotenv

# ============================================================
# 关键: 在任何 import 之前设置环境变量，强制所有模型缓存到项目内部
# ============================================================

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 加载 .env 文件中的环境变量（API key 等），.env 已在 .gitignore 中，不会提交到 git
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

_MODEL_CACHE_DIR = os.path.join(_PROJECT_ROOT, "data", "model_cache")
os.environ["MODELSCOPE_CACHE"] = os.path.join(_MODEL_CACHE_DIR, "modelscope")
os.environ["HF_HOME"] = os.path.join(_MODEL_CACHE_DIR, "huggingface")
os.environ["HUGGINGFACE_HUB_CACHE"] = os.path.join(_MODEL_CACHE_DIR, "huggingface", "hub")
os.environ["SENTENCE_TRANSFORMERS_HOME"] = os.path.join(_MODEL_CACHE_DIR, "huggingface")

_FFMPEG_DIR = os.path.join(_PROJECT_ROOT, "tools", "ffmpeg", "bin")
if os.path.isdir(_FFMPEG_DIR):
    os.environ["PATH"] = _FFMPEG_DIR + os.pathsep + os.environ.get("PATH", "")

# LibreOffice 路径检测（项目内置 > 系统 PATH）
_LO_SOFFICE = None
_LO_CANDIDATES = [
    os.path.join(_PROJECT_ROOT, "tools", "LibreOffice", "program", "soffice.exe"),
    os.path.join(
        _PROJECT_ROOT,
        "tools",
        "LibreOffice",
        "LibreOfficePortable",
        "App",
        "libreoffice",
        "program",
        "soffice.exe",
    ),
]
for _candidate in _LO_CANDIDATES:
    if os.path.isfile(_candidate):
        _LO_SOFFICE = _candidate
        _LO_BIN_DIR = os.path.dirname(_candidate)
        os.environ["PATH"] = _LO_BIN_DIR + os.pathsep + os.environ.get("PATH", "")
        break

for _d in [
    os.environ["MODELSCOPE_CACHE"],
    os.environ["HF_HOME"],
    os.environ["HUGGINGFACE_HUB_CACHE"],
]:
    os.makedirs(_d, exist_ok=True)

# ============================================================
# 正常导入
# ============================================================

import logging  # noqa: E402
import re  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any  # noqa: E402

import yaml  # noqa: E402

logger = logging.getLogger(__name__)


# ============================================================
# 异常定义
# ============================================================


class LectureAssistantError(Exception):
    """项目根异常。"""

    pass


class ConfigurationError(LectureAssistantError):
    """配置错误。"""

    pass


# ============================================================
# 配置数据类
# ============================================================


@dataclass
class ProjectConfig:
    name: str = "Lecture Assistant"
    data_dir: str = "data"


@dataclass
class ASRConfig:
    model: str = "iic/SenseVoiceSmall"
    device: str = "cpu"
    language: str = "zh"
    use_timestamps: bool = True
    batch_size: int = 1


@dataclass
class ParserConfig:
    backend: str = "magic-pdf"
    enable_formula_recognition: bool = True
    enable_table_recognition: bool = True
    output_image_format: str = "png"
    method: str = "auto"


@dataclass
class LLMConfig:
    provider: str = "deepseek"
    api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    base_url: str = "https://api.deepseek.com/v1"
    model: str = "deepseek-chat"
    max_tokens: int = 4096
    temperature: float = 0.3
    timeout: int = 120
    max_retries: int = 3


@dataclass
class EmbeddingConfig:
    model_name: str = "BAAI/bge-small-zh-v1.5"
    device: str = "cpu"
    normalize: bool = True


@dataclass
class ChromaDBConfig:
    persist_directory: str = "data/chroma_db"
    collection_name: str = "course_content"
    chunk_size: int = 800
    chunk_overlap: int = 150
    distance_metric: str = "cosine"


@dataclass
class UIConfig:
    title: str = "课堂助手 - Lecture Assistant"
    layout: str = "wide"
    sidebar_state: str = "expanded"
    max_upload_size_mb: int = 500


@dataclass
class AppConfig:
    project: ProjectConfig = field(default_factory=ProjectConfig)
    asr: ASRConfig = field(default_factory=ASRConfig)
    parser: ParserConfig = field(default_factory=ParserConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    chromadb: ChromaDBConfig = field(default_factory=ChromaDBConfig)
    ui: UIConfig = field(default_factory=UIConfig)


# ============================================================
# 配置加载
# ============================================================

_config: AppConfig | None = None

_ENV_VAR_RE = re.compile(r"\$\{([^}:]+)(?::([^}]*))?\}")


def _resolve_env_vars(raw_value: str) -> str:
    """解析字符串中的 ${VAR_NAME} 或 ${VAR_NAME:default} 环境变量引用。"""

    def _replace(match: re.Match) -> str:
        var_name = match.group(1)
        default_val = match.group(2)
        env_val = os.environ.get(var_name)
        if env_val is not None:
            return env_val
        if default_val is not None:
            return default_val
        raise ConfigurationError(
            f"环境变量 {var_name} 未设置，且无默认值。\n请设置: set {var_name}=your_value"
        )

    return _ENV_VAR_RE.sub(_replace, raw_value)


def _resolve_config_dict(d: dict) -> dict:
    """递归遍历配置字典，展开所有值中的环境变量引用。"""
    result = {}
    for key, value in d.items():
        if isinstance(value, dict):
            result[key] = _resolve_config_dict(value)
        elif isinstance(value, str):
            result[key] = _resolve_env_vars(value)
        else:
            result[key] = value
    return result


def _dict_to_dataclass(cls: type, data: dict) -> Any:
    """将字典递归转换为 dataclass 实例。"""
    field_types = {f.name: f.type for f in cls.__dataclass_fields__.values()}
    kwargs = {}
    for key, value in data.items():
        if key in field_types:
            ft = field_types[key]
            if isinstance(value, dict) and hasattr(ft, "__dataclass_fields__"):
                kwargs[key] = _dict_to_dataclass(ft, value)
            else:
                kwargs[key] = value
    return cls(**kwargs)


def get_config(config_path: Path | None = None) -> AppConfig:
    """获取全局配置单例。

    查找顺序:
    1. 传入的 config_path 参数
    2. 环境变量 LECTURE_ASSISTANT_CONFIG
    3. 项目根目录下的 config.yaml
    """
    global _config
    if _config is not None and config_path is None:
        return _config

    if config_path is None:
        env_path = os.environ.get("LECTURE_ASSISTANT_CONFIG")
        if env_path:
            config_path = Path(env_path)
        else:
            config_path = Path(_PROJECT_ROOT) / "config.yaml"

    config_path = Path(config_path).resolve()
    if not config_path.exists():
        raise ConfigurationError(
            f"配置文件不存在: {config_path}\n请复制 config.example.yaml 为 config.yaml 并修改配置"
        )

    logger.info("加载配置: %s", config_path)
    with open(config_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if raw is None:
        raise ConfigurationError(f"配置文件为空: {config_path}")

    resolved = _resolve_config_dict(raw)
    _config = _dict_to_dataclass(AppConfig, resolved)

    # 将 relative data_dir 转为绝对路径
    data_dir = Path(_PROJECT_ROOT) / _config.project.data_dir
    _config.project.data_dir = str(data_dir.resolve())

    logger.info("配置加载完成，data_dir=%s", _config.project.data_dir)
    return _config


def reload_config(config_path: Path | None = None) -> AppConfig:
    """强制重新加载配置（Streamlit 热更新时使用）。"""
    global _config
    _config = None
    return get_config(config_path)


def get_project_root() -> Path:
    """返回项目根目录的绝对路径。"""
    return Path(_PROJECT_ROOT).resolve()


def get_libreoffice_path() -> str | None:
    """返回 LibreOffice soffice.exe 路径（项目内置优先）。"""
    return _LO_SOFFICE


def get_magic_pdf_path() -> str:
    """返回 magic-pdf CLI 可执行文件路径。"""
    venv_scripts = Path(_PROJECT_ROOT) / ".venv" / "Scripts"
    for name in ["magic-pdf.exe", "magic-pdf"]:
        candidate = venv_scripts / name
        if candidate.exists():
            return str(candidate)
    return "magic-pdf"

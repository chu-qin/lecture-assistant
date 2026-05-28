"""文档解析抽象基类与数据契约。"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

# ============================================================
# 异常
# ============================================================


class ParserError(Exception):
    """文档解析模块基础异常。"""

    pass


class UnsupportedFormatError(ParserError):
    """不支持的文件格式。"""

    pass


class ParserExecutionError(ParserError):
    """解析执行失败。"""

    pass


# ============================================================
# 数据类
# ============================================================


@dataclass
class ParserResult:
    markdown_content: str
    output_dir: Path
    markdown_file: Path
    images: list[Path] = field(default_factory=list)
    tables_count: int = 0
    formulas_count: int = 0
    metadata: dict = field(default_factory=dict)


# ============================================================
# 抽象基类
# ============================================================


class BaseParser(ABC):
    @abstractmethod
    def parse(self, file_path: Path, output_dir: Path) -> ParserResult:
        """解析单个文档文件。"""
        ...

    @abstractmethod
    def parse_batch(self, file_paths: list[Path], output_dir: Path) -> list[ParserResult]:
        """批量解析多个文档文件。"""
        ...

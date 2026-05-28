"""MinerU magic-pdf 文档解析器 + PPT/PPTX 文本提取。

- PDF: magic-pdf CLI（子进程调用，支持公式/表格/图片）
- PPT/PPTX: python-pptx + olefile（纯 Python 文本提取，无需 LibreOffice）
"""

import logging
import os
import re
import subprocess
from pathlib import Path

from ..config import ParserConfig, get_magic_pdf_path
from .base import BaseParser, ParserExecutionError, ParserResult, UnsupportedFormatError
from .ppt_extractor import extract_text as extract_ppt_text


def get_parser(config: ParserConfig) -> "MinerUParser":
    """返回 MinerU 解析器实例（Streamlit 环境下缓存）。"""
    try:
        import streamlit as st

        @st.cache_resource
        def _cached(cfg: ParserConfig) -> "MinerUParser":
            return MinerUParser(cfg)

        return _cached(config)
    except (ImportError, ModuleNotFoundError):
        return MinerUParser(config)


logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = {".pdf", ".pptx", ".ppt"}


class MinerUParser(BaseParser):
    def __init__(self, config: ParserConfig):
        self._config = config
        self._magic_pdf_exe = get_magic_pdf_path()

    def parse(self, file_path: Path, output_dir: Path) -> ParserResult:
        file_path = Path(file_path).resolve()
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        ext = file_path.suffix.lower()
        if ext not in _SUPPORTED_EXTENSIONS:
            raise UnsupportedFormatError(f"不支持的文件格式: {ext}")

        output_dir = Path(output_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        # PPT/PPTX → 使用纯 Python 文本提取
        if ext in (".pptx", ".ppt"):
            return self._parse_ppt(file_path, output_dir)

        # PDF → 使用 magic-pdf CLI
        return self._parse_pdf(file_path, output_dir)

    def _parse_ppt(self, file_path: Path, output_dir: Path) -> ParserResult:
        logger.info("提取PPT文本: %s", file_path.name)

        try:
            markdown_content = extract_ppt_text(file_path)
        except Exception as e:
            raise ParserExecutionError(f"PPT 文本提取失败: {e}")

        if not markdown_content.strip():
            raise ParserExecutionError(
                f"未能从 {file_path.name} 中提取到文本内容。\n"
                "如果文件包含较多图片/图表，建议手动导出为 PDF 后再解析。"
            )

        basename = file_path.stem
        # 保存提取的 markdown
        output_subdir = output_dir / basename
        output_subdir.mkdir(parents=True, exist_ok=True)
        md_file = output_subdir / f"{basename}.md"
        md_file.write_text(markdown_content, encoding="utf-8")

        tables_count = self._extract_tables_count(markdown_content)
        formulas_count = self._extract_formulas_count(markdown_content)

        logger.info("PPT文本提取完成: %s (%d 字)", file_path.name, len(markdown_content))

        return ParserResult(
            markdown_content=markdown_content,
            output_dir=output_subdir,
            markdown_file=md_file,
            images=[],
            tables_count=tables_count,
            formulas_count=formulas_count,
            metadata={
                "source_file": file_path.name,
                "parser": "python-pptx+olefile",
                "method": "text_extraction",
            },
        )

    def _parse_pdf(self, file_path: Path, output_dir: Path) -> ParserResult:
        logger.info("开始解析 PDF: %s", file_path.name)

        method = self._config.method

        cmd = [
            self._magic_pdf_exe,
            "-p",
            str(file_path),
            "-o",
            str(output_dir),
            "-m",
            method,
            "-l",
            "zh",
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,
                cwd=str(output_dir),
                env=os.environ.copy(),
            )
            if result.returncode != 0:
                stderr = result.stderr or result.stdout or ""
                if "LibreOffice not found" in stderr or "soffice" in stderr.lower():
                    raise ParserExecutionError(
                        "PDF 解析需要 LibreOffice 的支持组件。\n"
                        "请安装 LibreOffice 后重试: https://www.libreoffice.org/download/"
                    )
                raise ParserExecutionError(f"magic-pdf 退出码 {result.returncode}: {stderr[-500:]}")
        except subprocess.TimeoutExpired:
            raise ParserExecutionError("magic-pdf 解析超时（超过 600 秒）")

        basename = file_path.stem
        output_subdir = output_dir / basename
        md_file = output_subdir / f"{basename}.md"

        if not md_file.exists():
            candidates = list(output_subdir.rglob("*.md"))
            cand2 = list(output_dir.rglob(f"{basename}*.md"))
            all_candidates = candidates + cand2
            if all_candidates:
                md_file = all_candidates[0]
            else:
                contents = list(output_dir.rglob("*"))[:30]
                raise ParserExecutionError(
                    f"magic-pdf 未生成 Markdown 文件。\n"
                    f"输出目录: {output_subdir}\n"
                    f"目录内容: {contents}"
                )

        markdown_content = md_file.read_text(encoding="utf-8")

        images: list[Path] = []
        for img_dir_candidate in [output_subdir / "images", output_subdir]:
            if img_dir_candidate.is_dir():
                images = sorted(
                    p
                    for p in img_dir_candidate.rglob("*")
                    if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".gif", ".bmp")
                )
                if images:
                    break

        tables_count = self._extract_tables_count(markdown_content)
        formulas_count = self._extract_formulas_count(markdown_content)

        logger.info(
            "PDF 解析完成: %s (公式=%d, 表格=%d, 图片=%d)",
            file_path.name,
            formulas_count,
            tables_count,
            len(images),
        )

        return ParserResult(
            markdown_content=markdown_content,
            output_dir=output_subdir,
            markdown_file=md_file,
            images=images,
            tables_count=tables_count,
            formulas_count=formulas_count,
            metadata={
                "source_file": file_path.name,
                "parser": "magic-pdf",
                "method": method,
            },
        )

    def parse_batch(self, file_paths: list[Path], output_dir: Path) -> list[ParserResult]:
        results: list[ParserResult] = []
        for fp in file_paths:
            try:
                result = self.parse(fp, output_dir)
                results.append(result)
            except Exception as e:
                logger.error("解析失败 [%s]: %s", fp.name, e)
                results.append(
                    ParserResult(
                        markdown_content="",
                        output_dir=output_dir,
                        markdown_file=Path(),
                        metadata={"source_file": fp.name, "error": str(e)},
                    )
                )
        return results

    @staticmethod
    def _extract_formulas_count(markdown: str) -> int:
        return len(re.findall(r"\$\$", markdown)) // 2

    @staticmethod
    def _extract_tables_count(markdown: str) -> int:
        return len(re.findall(r"\|[-\s|]+\|", markdown))

"""EPUB 电子书解析器 — ebooklib + html2text 转换为结构化 Markdown。"""

import logging
from pathlib import Path

from .base import BaseParser, ParserError, ParserResult, UnsupportedFormatError

logger = logging.getLogger(__name__)

_instance: "EpubParser | None" = None


def get_epub_parser() -> "EpubParser":
    """返回 EpubParser 单例（Streamlit 环境下缓存）。"""
    global _instance
    try:
        import streamlit as st

        @st.cache_resource
        def _cached() -> "EpubParser":
            return EpubParser()

        return _cached()
    except (ImportError, ModuleNotFoundError):
        if _instance is None:
            _instance = EpubParser()
        return _instance


class EpubParser(BaseParser):
    """EPUB 电子书解析器，将章节转换为结构化 Markdown。"""

    def parse(self, file_path: Path, output_dir: Path) -> ParserResult:
        file_path = Path(file_path).resolve()
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        ext = file_path.suffix.lower()
        if ext != ".epub":
            raise UnsupportedFormatError(f"Expected .epub file, got: {ext}")

        output_dir = Path(output_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        import ebooklib
        from ebooklib import epub

        try:
            book = epub.read_epub(str(file_path))
        except Exception as e:
            raise ParserError(f"Failed to open EPUB: {e}") from e

        title = self._get_metadata(book, "title", file_path.stem)
        author = self._get_metadata(book, "creator", "")

        import html2text

        h2t = html2text.HTML2Text()
        h2t.body_width = 0
        h2t.ignore_images = False
        h2t.images_to_alt = False
        h2t.ignore_links = False
        h2t.ignore_emphasis = False

        chapters: list[str] = []
        image_paths: list[Path] = []
        images_dir = output_dir / "images"
        images_dir.mkdir(exist_ok=True)

        chapter_count = 0
        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            if item.get_name() and "nav" in item.get_name().lower():
                continue
            try:
                content = item.get_content().decode("utf-8")
            except UnicodeDecodeError:
                try:
                    content = item.get_content().decode("latin-1")
                except Exception:
                    logger.warning("Cannot decode item: %s", item.get_name())
                    continue

            try:
                md = h2t.handle(content)
            except Exception:
                logger.warning("html2text failed for: %s", item.get_name())
                continue

            if not md.strip():
                continue

            chapter_count += 1
            chapter_title = self._get_item_title(item, chapter_count)
            chapters.append(f"## {chapter_title}\n\n{md.strip()}")

        for item in book.get_items_of_type(ebooklib.ITEM_IMAGE):
            try:
                img_name = Path(item.get_name()).name or f"image_{item.id}.jpg"
                img_path = images_dir / img_name
                img_path.write_bytes(item.get_content())
                image_paths.append(img_path)
            except Exception:
                pass

        if chapter_count == 0:
            raise ParserError("No readable chapters found in EPUB.")

        md_lines = [f"# {title}\n"]
        if author:
            md_lines.append(f"**Author**: {author}\n")
        md_lines.append("")
        md_lines.append("\n\n".join(chapters))
        markdown_content = "\n".join(md_lines)

        safe_name = (
            "".join(c for c in title if c.isalnum() or c in " _-").strip() or file_path.stem
        )
        md_file = output_dir / f"{safe_name}.md"
        md_file.write_text(markdown_content, encoding="utf-8")

        logger.info(
            "EPUB parsed: %s (chapters=%d, images=%d, chars=%d)",
            file_path.name,
            chapter_count,
            len(image_paths),
            len(markdown_content),
        )

        return ParserResult(
            markdown_content=markdown_content,
            output_dir=output_dir,
            markdown_file=md_file,
            images=image_paths,
            tables_count=0,
            formulas_count=0,
            metadata={
                "source_file": file_path.name,
                "title": title,
                "author": author,
                "chapter_count": chapter_count,
                "parser": "ebooklib+html2text",
            },
        )

    def parse_batch(self, file_paths: list[Path], output_dir: Path) -> list[ParserResult]:
        results: list[ParserResult] = []
        for fp in file_paths:
            try:
                result = self.parse(fp, output_dir)
                results.append(result)
            except Exception as e:
                logger.error("EPUB parse failed [%s]: %s", fp.name, e)
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
    def _get_metadata(book, key: str, default: str = "") -> str:
        try:
            items = book.get_metadata("DC", key)
            if items and items[0][0]:
                return str(items[0][0])
        except Exception:
            pass
        return default

    @staticmethod
    def _get_item_title(item, index: int) -> str:
        try:
            title = item.get_name()
            if title:
                return Path(title).stem.replace("_", " ").replace("-", " ")
        except Exception:
            pass
        return f"Chapter {index}"

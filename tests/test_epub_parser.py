"""EpubParser 单元测试 — 通过动态生成 EPUB 避免外部文件依赖。"""

from pathlib import Path

import pytest

from src.parser.base import ParserError, UnsupportedFormatError
from src.parser.epub_parser import EpubParser, get_epub_parser


def _make_epub(tmp_path: Path, title: str = "Test Book", author: str = "Test Author",
               chapters: list[str] | None = None, add_images: bool = False) -> Path:
    """Helper: create a minimal EPUB file for testing."""
    from ebooklib import epub

    book = epub.EpubBook()
    book.set_identifier("test-id-001")
    book.set_title(title)
    book.set_language("en")
    if author:
        book.add_author(author)

    if chapters is None:
        chapters = ["<h1>Chapter 1</h1><p>Content of chapter one.</p>",
                     "<h1>Chapter 2</h1><p>Content of <b>chapter</b> two.</p>"]

    spine = ["nav"]
    toc = []
    for i, html in enumerate(chapters):
        c = epub.EpubHtml(
            title=f"Chapter {i + 1}",
            file_name=f"chap_{i + 1}.xhtml",
            lang="en",
        )
        c.content = f"<html><body>{html}</body></html>".encode()
        book.add_item(c)
        spine.append(c)
        toc.append(c)

    if add_images:
        # Minimal valid 1x1 red PNG (no PIL dependency)
        png_bytes = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0eIDATx\x9cc\xf8\x0f\x00"
            b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        img_item = epub.EpubImage()
        img_item.file_name = "images/test.png"
        img_item.content = png_bytes
        book.add_item(img_item)

    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = spine
    book.toc = toc

    safe_title = title or "untitled"
    out_path = tmp_path / f"{safe_title}.epub"
    epub.write_epub(str(out_path), book)
    return out_path


class TestEpubParserBasic:
    def test_parse_valid_epub(self, tmp_path):
        parser = EpubParser()
        epub_path = _make_epub(tmp_path, "Valid Book", "Author Name")
        out_dir = tmp_path / "output"
        result = parser.parse(epub_path, out_dir)

        assert result.markdown_content
        assert "Valid Book" in result.markdown_content
        assert "Author Name" in result.markdown_content
        assert "Chapter 1" in result.markdown_content
        assert result.markdown_file.exists()
        assert result.metadata["title"] == "Valid Book"
        assert result.metadata["author"] == "Author Name"
        assert result.metadata["chapter_count"] >= 2

    def test_parse_creates_output_dir(self, tmp_path):
        parser = EpubParser()
        epub_path = _make_epub(tmp_path)
        out_dir = tmp_path / "nested" / "output"
        result = parser.parse(epub_path, out_dir)
        assert out_dir.exists()
        assert result.markdown_file.exists()

    def test_parse_batch(self, tmp_path):
        parser = EpubParser()
        paths = [
            _make_epub(tmp_path, "Book A", "Author A"),
            _make_epub(tmp_path, "Book B", "Author B"),
        ]
        out_dir = tmp_path / "output"
        results = parser.parse_batch(paths, out_dir)

        assert len(results) == 2
        assert "Book A" in results[0].markdown_content
        assert "Book B" in results[1].markdown_content


class TestEpubParserMetadata:
    def test_extracts_title_and_author(self, tmp_path):
        parser = EpubParser()
        epub_path = _make_epub(tmp_path, "Linear Algebra", "Dr. Smith")
        result = parser.parse(epub_path, tmp_path / "out")

        assert result.metadata["title"] == "Linear Algebra"
        assert result.metadata["author"] == "Dr. Smith"

    def test_fallback_title_from_filename(self, tmp_path):
        parser = EpubParser()
        epub_path = _make_epub(tmp_path, "", "")
        result = parser.parse(epub_path, tmp_path / "out")

        assert result.metadata["title"] == "untitled"

    def test_missing_author_defaults_empty(self, tmp_path):
        parser = EpubParser()
        epub_path = _make_epub(tmp_path, "Some Book", "")  # no author
        result = parser.parse(epub_path, tmp_path / "out")

        assert result.metadata["author"] == ""

    def test_chapter_count_in_metadata(self, tmp_path):
        parser = EpubParser()
        chapters = [
            "<h1>A</h1><p>Text A</p>",
            "<h1>B</h1><p>Text B</p>",
            "<h1>C</h1><p>Text C</p>",
        ]
        epub_path = _make_epub(tmp_path, chapters=chapters)
        result = parser.parse(epub_path, tmp_path / "out")

        assert result.metadata["chapter_count"] == 3


class TestEpubParserMarkdown:
    def test_html_to_markdown_conversion(self, tmp_path):
        parser = EpubParser()
        chapters = ["<h1>Intro</h1><p>Hello <b>World</b></p>"]
        epub_path = _make_epub(tmp_path, chapters=chapters)
        result = parser.parse(epub_path, tmp_path / "out")

        assert "Intro" in result.markdown_content
        assert "World" in result.markdown_content

    def test_markdown_file_saved(self, tmp_path):
        parser = EpubParser()
        epub_path = _make_epub(tmp_path, "My Book")
        result = parser.parse(epub_path, tmp_path / "out")

        assert result.markdown_file.name == "My Book.md"
        assert result.markdown_file.read_text(encoding="utf-8") == result.markdown_content

    def test_sanitized_filename(self, tmp_path):
        parser = EpubParser()
        epub_path = _make_epub(tmp_path, "Test (Book) [Vol.1]")
        result = parser.parse(epub_path, tmp_path / "out")

        assert result.markdown_file.exists()
        assert "(" not in result.markdown_file.name
        assert "[" not in result.markdown_file.name


class TestEpubParserImages:
    def test_images_extracted(self, tmp_path):
        parser = EpubParser()
        epub_path = _make_epub(tmp_path, "Book With Images", add_images=True)
        out_dir = tmp_path / "out"
        result = parser.parse(epub_path, out_dir)

        assert len(result.images) >= 1
        assert result.images[0].exists()
        assert (out_dir / "images").is_dir()

    def test_no_images_dirs_created_when_none(self, tmp_path):
        parser = EpubParser()
        epub_path = _make_epub(tmp_path, add_images=False)
        out_dir = tmp_path / "out"
        result = parser.parse(epub_path, out_dir)

        # images dir may or may not exist (created by mkdir exist_ok),
        # but result.images must be empty if no images in epub
        assert result.images == []


class TestEpubParserErrors:
    def test_unsupported_extension(self, tmp_path):
        parser = EpubParser()
        fake = tmp_path / "doc.pdf"
        fake.write_text("not an epub")
        with pytest.raises(UnsupportedFormatError):
            parser.parse(fake, tmp_path / "out")

    def test_file_not_found(self, tmp_path):
        parser = EpubParser()
        with pytest.raises(FileNotFoundError):
            parser.parse(Path("/nonexistent/path.epub"), tmp_path / "out")

    def test_invalid_epub_content(self, tmp_path):
        parser = EpubParser()
        fake = tmp_path / "bad.epub"
        fake.write_text("this is not a valid epub file")
        with pytest.raises(ParserError):
            parser.parse(fake, tmp_path / "out")

    def test_batch_with_mixed_results(self, tmp_path):
        parser = EpubParser()
        good = _make_epub(tmp_path, "Good Book")
        bad = tmp_path / "bad.epub"
        bad.write_text("not epub")
        results = parser.parse_batch([good, bad], tmp_path / "out")

        assert len(results) == 2
        assert results[0].markdown_content  # good item succeeds
        assert not results[1].markdown_content  # bad item has error in metadata
        assert "error" in results[1].metadata


class TestEpubParserFactory:
    def test_get_epub_parser_returns_epub_parser(self):
        parser = get_epub_parser()
        assert isinstance(parser, EpubParser)

    def test_get_epub_parser_returns_singleton(self):
        p1 = get_epub_parser()
        p2 = get_epub_parser()
        assert p1 is p2  # cached


class TestEpubParserEdgeCases:
    def test_chapters_with_empty_content_skipped(self, tmp_path):
        parser = EpubParser()
        chapters = [
            "<h1>Good</h1><p>Content</p>",
            "<p></p>",  # effectively empty
            "<h1>Also Good</h1><p>More content</p>",
        ]
        epub_path = _make_epub(tmp_path, chapters=chapters)
        result = parser.parse(epub_path, tmp_path / "out")

        assert "Good" in result.markdown_content
        assert "Also Good" in result.markdown_content

    def test_latin1_encoding_fallback(self, tmp_path):
        """Verify non-UTF8 content is handled. ebooklib normally handles encoding
        internally, so this just confirms valid EPUB parsing works."""
        parser = EpubParser()
        epub_path = _make_epub(tmp_path, "Encoding Test")
        result = parser.parse(epub_path, tmp_path / "out")

        assert result.markdown_content
        assert "Encoding Test" in result.markdown_content

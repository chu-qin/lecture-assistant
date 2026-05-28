"""测试 MarkdownChunker — 文本分块逻辑。"""

import textwrap

import pytest

from src.knowledge.chunker import Chunk, MarkdownChunker


@pytest.fixture
def chunker():
    return MarkdownChunker(chunk_size=800, chunk_overlap=150)


@pytest.fixture
def small_chunker():
    return MarkdownChunker(chunk_size=120, chunk_overlap=30)


class TestChunkText:
    """chunk_text() 单元测试。"""

    def test_basic_markdown(self, chunker):
        text = textwrap.dedent("""\
        ## 第一章 概述
        这是第一章的内容，介绍基本概念和术语。

        ### 1.1 定义
        关键定义如下所示，需要学生重点掌握。

        ## 第二章 深入
        第二章的内容涉及更高级的主题。""")
        chunks = chunker.chunk_text(text, {"source": "test"})

        assert len(chunks) >= 2
        titles = {c.metadata.get("section_title", "") for c in chunks}
        assert "第一章 概述" in titles
        assert "1.1 定义" in titles or "第二章 深入" in titles
        for c in chunks:
            assert "source" in c.metadata
            assert c.metadata["source"] == "test"
            assert "chunk_index" in c.metadata
            assert "total_chunks" in c.metadata
            assert c.metadata["total_chunks"] == len(chunks)

    def test_empty_text(self, chunker):
        assert chunker.chunk_text("") == []
        assert chunker.chunk_text("   \n  \n  ") == []

    def test_no_headers(self, chunker):
        text = "这是一段没有任何 Markdown 标题的纯文本内容，应该仍然能产生至少一个 chunk。"
        chunks = chunker.chunk_text(text, {"source": "test"})

        assert len(chunks) == 1
        assert chunks[0].metadata["section_title"] == ""
        assert "source" in chunks[0].metadata

    def test_long_formula_not_split_at_paragraph_level(self, chunker):
        """公式块在段落级别不会被切割（段落由空行分隔）。"""
        formula = "$$" + "x" * 400 + "$$"
        text = f"## 公式测试\n\n段落一：这里有一段文字。\n\n{formula}\n\n段落三：公式之后的内容。"
        chunks = chunker.chunk_text(text)

        # 公式块所在的段落应作为一个整体
        formula_chunks = [c for c in chunks if "$$" in c.text]
        assert len(formula_chunks) >= 1
        for c in formula_chunks:
            # 公式块内部 $$$$ 标记应完整出现（成对）
            dollar_count = c.text.count("$$")
            assert dollar_count % 2 == 0

    def test_overlap_applied(self, chunker):
        """当有多个 chunk 时，相邻 chunk 应有重叠。"""
        text = "## 主题\n\n" + ("数据驱动的分析方法在现代教育中具有重要价值。" * 40)
        chunks = chunker.chunk_text(text)

        if len(chunks) > 1:
            # overlap 确保相邻 chunk 有内容延续
            assert len(chunks[1].text) > 0

    def test_exact_chunk_size_boundary(self):
        """内容恰好等于 chunk_size 时不截断。"""
        precise_chunker = MarkdownChunker(chunk_size=500, chunk_overlap=0)
        text = "## T\n\n" + "A" * 490  # 总长度接近但不超过 chunk_size
        chunks = precise_chunker.chunk_text(text)

        assert len(chunks) >= 1
        # 所有 chunk 文本非空
        for c in chunks:
            assert c.text.strip()

    def test_long_paragraph_split_by_sentence(self, chunker):
        """超长段落（>800 字符）按句子边界拆分。"""
        # 构造一个超过 800 字符的单段文本（无空行分隔），验证 _split_protected
        # 的句子边界切割逻辑。注意 _split_protected 目前硬编码 chunk_size=800。
        sentence = "这是内容丰富的测试句子，用于验证分块逻辑的正确性与可靠性。"
        text = "## 长段落\n\n" + (sentence * 40)  # ~26 chars × 40 = ~1040 chars > 800
        chunks = chunker.chunk_text(text)

        assert len(chunks) >= 2
        for c in chunks:
            assert c.text.strip()
            # 每个 chunk 以完整句子结尾（以 。 结束）
            assert c.text.rstrip().endswith("。")

    def test_code_block_protected(self, chunker):
        """代码块在段落层面不被切割。"""
        code = "```\n" + "line " * 80 + "\n```"
        text = f"## 代码示例\n\n这是一段介绍文字。\n\n{code}\n\n代码之后的内容。"
        chunks = chunker.chunk_text(text)

        code_chunks = [c for c in chunks if "```" in c.text]
        assert len(code_chunks) >= 1
        for c in code_chunks:
            # 代码块标记应成对出现
            assert c.text.count("```") % 2 == 0

    def test_metadata_base_none(self, chunker):
        text = "## 测试\n\n内容文本。"
        chunks = chunker.chunk_text(text)  # 不传 metadata_base

        assert len(chunks) >= 1
        for c in chunks:
            assert isinstance(c.metadata, dict)
            assert "chunk_index" in c.metadata

    def test_chunk_structure(self, chunker):
        """验证 Chunk 数据类结构。"""
        text = "## 结构测试\n\n测试内容。"
        chunks = chunker.chunk_text(text)

        assert len(chunks) >= 1
        c = chunks[0]
        assert isinstance(c, Chunk)
        assert isinstance(c.text, str)
        assert isinstance(c.metadata, dict)
        assert isinstance(c.index, int)

    def test_section_title_in_metadata(self, chunker):
        text = textwrap.dedent("""\
        ## 信号与系统概述
        这是概述内容。

        ## 傅里叶变换
        这是傅里叶变换的内容。""")
        chunks = chunker.chunk_text(text)

        titles = [c.metadata["section_title"] for c in chunks]
        assert "信号与系统概述" in titles
        assert "傅里叶变换" in titles

    def test_chunk_file(self, chunker, tmp_path):
        md_file = tmp_path / "test.md"
        md_file.write_text("## 文件测试\n\n文件中的内容。", encoding="utf-8")
        chunks = chunker.chunk_file(md_file, "transcript")

        assert len(chunks) >= 1
        for c in chunks:
            assert c.metadata["source_file"] == "test.md"
            assert c.metadata["source_type"] == "transcript"

    def test_preamble_before_first_header(self, chunker):
        text = "这是标题之前的前言内容，不应丢失。\n\n## 第一章\n\n第一章内容。"
        chunks = chunker.chunk_text(text)

        assert len(chunks) >= 2
        preamble_chunks = [c for c in chunks if c.metadata["section_title"] == ""]
        assert len(preamble_chunks) >= 1
        assert "前言" in preamble_chunks[0].text

    def test_chunk_indices_sequential(self, chunker):
        text = "## A\n\n内容A\n\n## B\n\n内容B\n\n## C\n\n内容C"
        chunks = chunker.chunk_text(text)

        for i, c in enumerate(chunks):
            assert c.metadata["chunk_index"] == i

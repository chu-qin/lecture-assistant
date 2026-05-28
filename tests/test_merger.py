"""测试 ContentMerger — 课件与转录内容合并逻辑。"""


import pytest

from src.merger.content_merger import ContentMerger, MergedContent


@pytest.fixture
def merger():
    return ContentMerger()


class TestMerge:
    """ContentMerger.merge() 单元测试。"""

    def test_both_sources(self, merger):
        transcript = "这是课堂讲解的转录文本。"
        parsed_docs = ["# 课件一\n\n课件内容。"]
        doc_metas = [{"source_file": "lecture1.pptx"}]

        result = merger.merge(
            transcript=transcript,
            parsed_docs=parsed_docs,
            doc_metas=doc_metas,
        )

        assert "课堂内容整理" in result.content
        assert "课件内容" in result.content
        assert "课堂讲解转录" in result.content
        assert "transcript" in result.sections
        assert "courseware" in result.sections
        assert result.sections["transcript"] == transcript
        assert result.metadata["has_transcript"] == "True"
        assert result.metadata["has_courseware"] == "True"

    def test_transcript_only(self, merger):
        result = merger.merge(transcript="只有转录。")

        assert "课堂讲解转录" in result.content
        assert "transcript" in result.sections
        assert "courseware" not in result.sections
        assert result.metadata["has_transcript"] == "True"
        assert result.metadata["has_courseware"] == "False"

    def test_courseware_only(self, merger):
        parsed_docs = ["# 课件\n\n内容。"]
        doc_metas = [{"source_file": "slides.pdf"}]

        result = merger.merge(parsed_docs=parsed_docs, doc_metas=doc_metas)

        assert "课件内容" in result.content
        assert "courseware" in result.sections
        assert "transcript" not in result.sections
        assert result.metadata["has_courseware"] == "True"
        assert result.metadata["has_transcript"] == "False"
        assert len(result.source_files) == 1

    def test_neither(self, merger):
        result = merger.merge()

        assert "课堂内容整理" in result.content
        assert result.sections == {}
        assert result.source_files == []
        assert result.metadata["has_transcript"] == "False"
        assert result.metadata["has_courseware"] == "False"

    def test_metadata_propagation(self, merger):
        transcript_meta = {"时长": "45分钟", "主讲人": "张老师"}
        result = merger.merge(
            transcript="转录内容。",
            transcript_meta=transcript_meta,
        )

        assert "45分钟" in result.content
        assert "张老师" in result.content

    def test_multiple_docs(self, merger):
        parsed_docs = ["# 课件一\n\nAAA", "# 课件二\n\nBBB", "# 课件三\n\nCCC"]
        doc_metas = [
            {"source_file": "ch1.pptx"},
            {"source_file": "ch2.pptx"},
            {"source_file": "ch3.pptx"},
        ]

        result = merger.merge(parsed_docs=parsed_docs, doc_metas=doc_metas)

        assert len(result.source_files) == 3
        assert "ch1.pptx" in result.content
        assert "ch2.pptx" in result.content
        assert "ch3.pptx" in result.content
        assert "AAA" in result.sections["courseware"]
        assert "BBB" in result.sections["courseware"]
        assert "CCC" in result.sections["courseware"]

    def test_merge_time_present(self, merger):
        result = merger.merge(transcript="test")

        assert "merge_time" in result.metadata
        assert result.metadata["merge_time"]  # 非空

    def test_word_count_in_metadata(self, merger):
        result = merger.merge(transcript="这是一段测试文本。")

        word_count = int(result.metadata["word_count"])
        assert word_count > 0

    def test_result_type(self, merger):
        result = merger.merge()

        assert isinstance(result, MergedContent)
        assert isinstance(result.content, str)
        assert isinstance(result.sections, dict)
        assert isinstance(result.metadata, dict)
        assert isinstance(result.source_files, list)

    def test_parsed_docs_without_metas(self, merger):
        """doc_metas 为 None 时使用默认标签。"""
        parsed_docs = ["文档内容。"]
        result = merger.merge(parsed_docs=parsed_docs)

        assert "课件_1" in result.content
        assert result.source_files == []


class TestToMarkdown:
    """ContentMerger.to_markdown() 单元测试。"""

    def test_writes_file(self, merger, tmp_path):
        merged = merger.merge(transcript="测试转录。")
        output = tmp_path / "subdir" / "out.md"

        result = merger.to_markdown(merged, output)

        assert result == output
        assert output.exists()
        content = output.read_text(encoding="utf-8")
        assert "测试转录" in content

    def test_creates_parent_dirs(self, merger, tmp_path):
        merged = merger.merge()
        output = tmp_path / "a" / "b" / "c" / "merged.md"

        merger.to_markdown(merged, output)

        assert output.exists()

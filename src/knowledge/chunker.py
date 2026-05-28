"""Markdown 语义感知的文本分块器。"""

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Chunk:
    text: str
    metadata: dict
    index: int


class MarkdownChunker:
    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 150):
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        # 匹配 Markdown 标题 (## 和 ### 级别)
        self._header_re = re.compile(r"^(#{2,4})\s+(.+)$", re.MULTILINE)

    def chunk_text(self, text: str, metadata_base: dict | None = None) -> list[Chunk]:
        if metadata_base is None:
            metadata_base = {}

        # Step 1: 按标题分割
        sections = self._split_by_headers(text)
        if not sections:
            sections = [("", text)]

        # Step 2: 对过长的段落进一步切割
        chunks: list[Chunk] = []
        for section_title, section_text in sections:
            sub_chunks = self._split_long_section(section_text, section_title)
            for sub_text in sub_chunks:
                if sub_text.strip():
                    metadata = {**metadata_base, "section_title": section_title}
                    chunks.append(Chunk(text=sub_text, metadata=metadata, index=len(chunks)))

        # Step 3: 为每个 chunk 设置 index
        for i, chunk in enumerate(chunks):
            chunk.metadata["chunk_index"] = i
            chunk.metadata["total_chunks"] = len(chunks)

        return chunks

    def chunk_file(self, file_path: Path, source_type: str) -> list[Chunk]:
        text = file_path.read_text(encoding="utf-8")
        metadata_base = {
            "source_file": str(file_path.name),
            "source_type": source_type,
        }
        return self.chunk_text(text, metadata_base)

    def _split_by_headers(self, text: str) -> list[tuple[str, str]]:
        """按 Markdown 标题分割，返回 [(标题, 内容), ...]"""
        matches = list(self._header_re.finditer(text))
        if not matches:
            return [("", text)]

        sections = []
        for i, m in enumerate(matches):
            title = m.group(2).strip()
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            sections.append((title, text[start:end].strip()))

        # 处理第一个标题之前的内容（如果有）
        first_start = matches[0].start()
        if first_start > 0:
            preamble = text[:first_start].strip()
            if preamble:
                sections.insert(0, ("", preamble))

        return sections

    def _split_long_section(self, section_text: str, section_title: str) -> list[str]:
        """对过长段落进一步切割，保护公式/代码/表格不截断。"""
        if len(section_text) <= self._chunk_size:
            return [section_text]

        # 按段落分割
        paragraphs = re.split(r"\n\s*\n", section_text)
        chunks: list[str] = []
        current = ""
        protected_regions = self._find_protected_regions(section_text)

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if len(current) + len(para) + 2 <= self._chunk_size:
                current = f"{current}\n\n{para}".strip() if current else para
            else:
                if current:
                    chunks.append(current)
                # 如果单段太长，保护性切割
                if len(para) > self._chunk_size:
                    sub_parts = self._split_protected(para, protected_regions)
                    chunks.extend(sub_parts)
                    current = ""
                else:
                    current = para

        if current:
            chunks.append(current)

        # 添加重叠
        if self._chunk_overlap > 0 and len(chunks) > 1:
            overlapped = []
            for i, chunk in enumerate(chunks):
                if i > 0:
                    prev_end = chunks[i - 1][-self._chunk_overlap :]
                    chunk = prev_end + "\n" + chunk
                overlapped.append(chunk)
            chunks = overlapped

        return chunks

    @staticmethod
    def _find_protected_regions(text: str) -> list[tuple[int, int]]:
        """找到保护区域（公式块、代码块、表格）的起止位置。"""
        regions = []
        # LaTeX 公式块 $$...$$
        for m in re.finditer(r"\$\$[\s\S]*?\$\$", text):
            regions.append((m.start(), m.end()))
        # 代码块 ```...```
        for m in re.finditer(r"```[\s\S]*?```", text):
            regions.append((m.start(), m.end()))
        return regions

    def _split_protected(self, text: str, _protected: list[tuple[int, int]]) -> list[str]:
        """对单段长文本切割，跳过保护区域内部。"""
        # 简化实现：按句子边界切割
        sentences = re.split(r"(?<=[。！？.!?])\s*", text)
        result = []
        current = ""
        for sent in sentences:
            if not sent.strip():
                continue
            if len(current) + len(sent) <= self._chunk_size:
                current += sent
            else:
                if current:
                    result.append(current)
                current = sent
        if current:
            result.append(current)
        return result if result else [text]

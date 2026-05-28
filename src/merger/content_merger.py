"""内容合并模块：将转录文本和课件解析结果合并为统合 Markdown。"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class MergedContent:
    content: str
    sections: dict[str, str] = field(default_factory=dict)
    source_files: list[Path] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class ContentMerger:
    def merge(
        self,
        transcript: str | None = None,
        parsed_docs: list[str] | None = None,
        transcript_meta: dict | None = None,
        doc_metas: list[dict] | None = None,
    ) -> MergedContent:
        """合并转录文本和课件内容为统合 Markdown。

        Args:
            transcript: 转录全文（可选）
            parsed_docs: 解析后的课件 Markdown 列表（可选）
            transcript_meta: 转录元数据
            doc_metas: 课件元数据列表

        Returns:
            MergedContent: 合并后的结构化内容
        """
        parts: list[str] = []
        sections: dict[str, str] = {}
        source_files: list[Path] = []

        # 文档头部
        parts.append("# 课堂内容整理")
        parts.append(f"\n> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        # 课件部分
        if parsed_docs:
            parts.append("\n---\n")
            parts.append("## 📚 课件内容\n")
            doc_texts = []
            for i, doc_md in enumerate(parsed_docs):
                label = f"课件_{i + 1}"
                if doc_metas and i < len(doc_metas):
                    source = doc_metas[i].get("source_file", label)
                    source_files.append(Path(source))
                    label = Path(source).name
                parts.append(f"### {label}\n")
                parts.append(doc_md)
                parts.append("")
                doc_texts.append(doc_md)
            sections["courseware"] = "\n\n".join(doc_texts)

        # 转录部分
        if transcript:
            parts.append("\n---\n")
            parts.append("## 🎤 课堂讲解转录\n")
            if transcript_meta:
                for k, v in transcript_meta.items():
                    parts.append(f"> {k}: {v}")
                parts.append("")
            parts.append(transcript)
            sections["transcript"] = transcript

        content = "\n".join(parts)
        metadata = {
            "merge_time": datetime.now().isoformat(),
            "word_count": str(len(content)),
            "has_transcript": str(transcript is not None),
            "has_courseware": str(parsed_docs is not None),
        }

        return MergedContent(
            content=content,
            sections=sections,
            source_files=source_files,
            metadata=metadata,
        )

    def to_markdown(self, merged: MergedContent, output_path: Path) -> Path:
        """将合并内容写入 Markdown 文件。"""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(merged.content, encoding="utf-8")
        return output_path

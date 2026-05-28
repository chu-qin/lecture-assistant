"""完整流程测试脚本：信号与系统"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.config import get_config
from src.course_manager import CourseManager

config = get_config()
cm = CourseManager(config.project.data_dir)

course_name = "信号与系统"
print(f"=== 创建课程: {course_name} ===")
cm.create_course(course_name)

# 源文件路径
source_dir = Path(r"C:\Users\Zhang_Qin\Desktop\信号与系统")
audio_files = sorted(source_dir.glob("*.m4a"))
ppt_files = sorted(source_dir.glob("*.ppt"))

print(f"\n音频文件 ({len(audio_files)}):")
for f in audio_files:
    print(f"  {f.name} ({f.stat().st_size / 1024 / 1024:.1f} MB)")

print(f"\nPPT文件 ({len(ppt_files)}):")
for f in ppt_files:
    print(f"  {f.name}")

# ====================================================================
# Step 1: 复制文件到课程目录
# ====================================================================
print("\n\n========== Step 1: 复制文件 ==========")

import shutil

for af in audio_files:
    dest = cm.sub_dir(course_name, "audio") / af.name
    if not dest.exists():
        shutil.copy2(af, dest)
        print(f"  已复制音频: {af.name}")
    else:
        print(f"  音频已存在: {af.name}")

for pf in ppt_files:
    dest = cm.sub_dir(course_name, "courseware") / pf.name
    if not dest.exists():
        shutil.copy2(pf, dest)
        print(f"  已复制PPT: {pf.name}")
    else:
        print(f"  PPT已存在: {pf.name}")

# ====================================================================
# Step 2: ASR 语音转写
# ====================================================================
print("\n\n========== Step 2: ASR 语音转写 ==========")

from src.asr.funasr_asr import FunASRSenseVoiceASR

asr = FunASRSenseVoiceASR(config.asr)

for af in audio_files:
    audio_path = cm.sub_dir(course_name, "audio") / af.name
    print(f"\n转录: {af.name} ...")
    try:
        result = asr.transcribe(audio_path)
        transcript_path = cm.sub_dir(course_name, "transcripts") / f"{af.stem}_transcript.txt"
        asr.save_transcript(result, transcript_path)
        print(
            f"  OK! 字数: {len(result.full_text)}, 片段: {len(result.segments)}, 时长: {result.duration_seconds:.0f}s"
        )

        # 保存前300字预览
        preview = result.full_text[:300]
        print(f"  预览: {preview}...")
    except Exception as e:
        print(f"  FAIL: {e}")

# ====================================================================
# Step 3: PPT 解析
# ====================================================================
print("\n\n========== Step 3: PPT 解析 ==========")

from src.parser.mineru_parser import MinerUParser

parser_config = config.parser
parser_config.method = "auto"
parser = MinerUParser(parser_config)

for pf in ppt_files:
    ppt_path = cm.sub_dir(course_name, "courseware") / pf.name
    output_dir = cm.sub_dir(course_name, "parsed_docs")
    print(f"\n解析: {pf.name} ...")
    try:
        result = parser.parse(ppt_path, output_dir)
        print(
            f"  OK! 公式: {result.formulas_count}, 表格: {result.tables_count}, 图片: {len(result.images)}"
        )
        preview = result.markdown_content[:300].replace("\n", " ")
        print(f"  预览: {preview}...")
    except Exception as e:
        print(f"  FAIL: {e}")

# ====================================================================
# Step 4: 内容合并
# ====================================================================
print("\n\n========== Step 4: 内容合并 ==========")

from src.merger.content_merger import ContentMerger

merger = ContentMerger()

# 读取解析结果
parsed_docs = []
parsed_dir = cm.sub_dir(course_name, "parsed_docs")
for md_file in sorted(parsed_dir.rglob("*.md")):
    if md_file.is_file():
        content = md_file.read_text(encoding="utf-8")
        parsed_docs.append(content)
        print(f"  已加载解析文档: {md_file.name} ({len(content)} 字)")

# 读取转录结果
transcript_text = ""
transcript_dir = cm.sub_dir(course_name, "transcripts")
for txt_file in sorted(transcript_dir.glob("*_transcript.txt")):
    if txt_file.is_file():
        text = txt_file.read_text(encoding="utf-8")
        transcript_text += text + "\n\n"
        print(f"  已加载转录: {txt_file.name} ({len(text)} 字)")

merged = merger.merge(
    transcript=transcript_text if transcript_text else None,
    parsed_docs=parsed_docs if parsed_docs else None,
)
merged_path = cm.sub_dir(course_name, "merged") / "merged_content.md"
merger.to_markdown(merged, merged_path)
print(f"\n合并完成! 总字数: {len(merged.content)}")
print(f"保存至: {merged_path}")

# ====================================================================
# Step 5: 复习资料生成 (如果 API Key 已设置)
# ====================================================================
print("\n\n========== Step 5: 复习资料生成 ==========")

if config.llm.api_key and "sk-" in config.llm.api_key:
    from src.llm.factory import get_llm

    llm = get_llm(config.llm)

    try:
        prompt = llm.load_prompt("review_generation.txt", content=merged.content[:8000])
    except Exception:
        prompt = merged.content[:8000] + "\n\n请根据以上内容生成复习提纲。"

    print(f"提示词长度: {len(prompt)} 字")
    print("正在调用 DeepSeek API...")

    try:
        response = llm.chat([{"role": "user", "content": prompt}], max_tokens=2048)
        print(f"OK! 回复长度: {len(response.content)} 字")
        print(f"Token 用量: {response.usage}")

        review_path = cm.sub_dir(course_name, "review_materials") / "review_material.md"
        review_path.write_text(response.content, encoding="utf-8")
        print(f"已保存至: {review_path}")

        # 预览前500字
        print(f"\n预览:\n{response.content[:500]}...")
    except Exception as e:
        print(f"FAIL: {e}")
else:
    print("跳过 (API Key 未设置)")

# ====================================================================
# Step 6: 知识库构建
# ====================================================================
print("\n\n========== Step 6: 知识库构建 ==========")

from src.knowledge.chroma_store import ChromaVectorStore
from src.knowledge.chunker import MarkdownChunker
from src.knowledge.embedder import SentenceTransformersEmbedder

try:
    print("加载 Embedding 模型...")
    embedder = SentenceTransformersEmbedder(config.embedding)
    chunker = MarkdownChunker(config.chromadb.chunk_size, config.chromadb.chunk_overlap)

    chroma_config = config.chromadb
    chroma_config.persist_directory = str(cm.chroma_dir(course_name))
    chroma_config.collection_name = cm.sanitize_collection_name(course_name)

    store = ChromaVectorStore(chroma_config, embedder)

    # 收集所有文本
    all_text = ""
    for md_file in sorted(parsed_dir.rglob("*.md")):
        if md_file.is_file():
            all_text += md_file.read_text(encoding="utf-8") + "\n\n"
    if transcript_text:
        all_text += transcript_text

    review_file = cm.sub_dir(course_name, "review_materials") / "review_material.md"
    if review_file.exists():
        all_text += "\n\n" + review_file.read_text(encoding="utf-8")

    print(f"总文本长度: {len(all_text)} 字")

    chunks = chunker.chunk_text(all_text, {"source_type": "courseware", "course": course_name})
    print(f"分块数: {len(chunks)}")

    if chunks:
        texts = [c.text for c in chunks]
        metadatas = [c.metadata for c in chunks]
        ids = store.add_documents(texts, metadatas)
        print(f"已导入 {len(ids)} 个文档块到 ChromaDB")

        # 测试检索
        results = store.search("信号与系统的基本概念", top_k=3)
        print("\n检索测试 (top 3):")
        for r in results:
            print(f"  [{r.score:.4f}] {r.content[:100]}...")
    else:
        print("分块为空，跳过导入")

    print("\n=== 流程测试完成! ===")
except Exception as e:
    print(f"FAIL: {e}")
    import traceback

    traceback.print_exc()

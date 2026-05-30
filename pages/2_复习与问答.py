"""课程工作台: 复习与问答 — 左栏资料查看/生成 + 右栏智能问答"""

from pathlib import Path

import streamlit as st

st.set_page_config(page_title="复习与问答", page_icon="", layout="wide")

import sys  # noqa: E402

_project_root = Path(__file__).resolve().parent.parent  # noqa: E402
if str(_project_root) not in sys.path:  # noqa: E402
    sys.path.insert(0, str(_project_root))  # noqa: E402

import json as _json_module  # noqa: E402
from datetime import datetime as _datetime  # noqa: E402

from src.i18n import t  # noqa: E402
from src.ui.session_state import get_state, init_session_state, set_state  # noqa: E402
from src.ui.sidebar import render_sidebar  # noqa: E402
from src.ui.theme import inject_mermaid, inject_workspace_layout  # noqa: E402

# ====================================================================
# 辅助函数（必须在页面逻辑之前定义）
# ====================================================================


def _material_type_short(material_type: str) -> str:
    """将资料类型映射为缩写（已 i18n）。"""
    type_to_key = {
        "复习提纲": "material.review_outline_short",
        "详细笔记": "material.detailed_notes_short",
        "知识结构图": "material.knowledge_map_short",
        "自测题库": "material.quiz_bank_short",
    }
    key = type_to_key.get(material_type)
    if key:
        return t(key)
    return material_type[:4]


def _normalize_latex(content: str) -> str:
    """标准化 LaTeX 分隔符，未配对的 $ 转义为 \\$ 避免 KaTeX 报错。

    采用字符级扫描器：正确配对的 $...$ / $$...$$ 保留为数学公式，
    配对失败的孤立 $ 转义为文本，从而防止 KaTeX 将后续中文当作数学模式解析。
    """
    import re

    # Step 1: 将 \( ... \) / \[ ... \] 统一为 $...$ / $$...$$
    content = re.sub(r"\\\(\s*", "$", content)
    content = re.sub(r"\s*\\\)", "$", content)
    content = re.sub(r"\\\[\s*", "$$", content)
    content = re.sub(r"\s*\\\]", "$$", content)

    # Step 2: 修复中文紧贴 $ 的问题
    content = re.sub(r"([一-鿿　-〿＀-￯])\$", r"\1 $", content)
    content = re.sub(r"\$([一-鿿　-〿＀-￯])", r"$ \1", content)

    # Step 3: 字符级扫描 — 配对 $ / $$，转义孤立 $
    return _scan_math_delimiters(content)


def _scan_math_delimiters(text: str) -> str:
    """逐字符扫描：匹配 $...$ 和 $$...$$，剥离内部 HTML，转义未闭合的 $。

    规则：
    - $$ 优先匹配（显示数学），找到最近的闭合 $$ → 保留为 $$...$$
    - 单个 $ 匹配最近的单个 $（跳过中间的 $$ 块）→ 保留为 $...$
    - 找不到闭合的 $ / $$ → 转义为 \\$ 或 \\$\\$，KaTeX 不作数学处理
    - 数学块内部的 HTML 标签会被剥离
    """
    import re

    _html_re = re.compile(r"<[^>]+>")

    result: list[str] = []
    i = 0
    n = len(text)

    while i < n:
        # ---- 显示数学 $$...$$ ----
        if i + 1 < n and text[i : i + 2] == "$$":
            closer = text.find("$$", i + 2)
            if closer != -1:
                inner = _html_re.sub("", text[i + 2 : closer])
                result.append("$$" + inner + "$$")
                i = closer + 2
            else:
                result.append("\\$\\$")
                i += 2
            continue

        # ---- 行内数学 $...$ ----
        if text[i] == "$":
            j = i + 1
            found = False
            while j < n:
                if text[j] == "$":
                    # 如果这个 $ 是 $$ 的起始，跳过整个 $$ 块继续搜索
                    if j + 1 < n and text[j : j + 2] == "$$":
                        closer2 = text.find("$$", j + 2)
                        if closer2 != -1:
                            j = closer2 + 2
                        else:
                            j += 2
                        continue
                    # 找到匹配的单个 $
                    inner = _html_re.sub("", text[i + 1 : j])
                    result.append("$" + inner + "$")
                    i = j + 1
                    found = True
                    break
                j += 1

            if not found:
                result.append("\\$")
                i += 1
            continue

        # ---- 普通文本 ----
        result.append(text[i])
        i += 1

    return "".join(result)


def _render_markdown(content: str) -> None:
    """渲染 Markdown，预处理 LaTeX 公式以保证正确显示。"""
    st.markdown(_normalize_latex(content))


def _build_type_sections(generate_types: list[str]) -> list[str]:
    """构建各类型的 prompt 片段（始终中文，发送给 LLM）。"""
    sections = []

    for gt in generate_types:
        if "复习提纲" in gt:
            sections.append("""
## 一、复习提纲

请为课程的每个章节生成详细的复习提纲，包括：
- **章节主题**：用一句话概括本章核心内容
- **核心概念清单**：列出本章所有重要概念，每个给出完整定义
- **重点标注**：用 ★ 标注重点（1-3 颗星表示重要程度），并说明为什么重要
- **难点标注**：用 ★★ 标注难点，详细解释难在哪里、如何理解
- **关键公式与定理**：完整列出（LaTeX 格式），附每个符号的含义、使用条件与前提假设、典型应用场景
- **常见误区**：本章学生最容易犯的 3-5 个错误
- **记忆技巧**：帮助记忆的口诀、类比或理解框架""")
        elif "详细笔记" in gt:
            sections.append("""
## 二、详细笔记（核心部分 —— 请务必极度详尽）

这是最重要的部分。请以「逐章逐节逐知识点」的方式，生成一份完整、详尽的课堂笔记。宁可过长也不要省略任何内容。

### 每章结构：
1. **章节导言**（3-5 句）：本章要解决什么问题？在学科中的位置是什么？
2. **知识点逐一详解**：按小节顺序，每个知识点包含：
   - **定义**：完整、严谨的定义
   - **背景与动机**：这个概念/定理是为了解决什么问题而提出的？
   - **详细解释**：用通俗语言和具体例子阐述
   - **公式推导**：所有公式给出完整推导过程或证明思路（LaTeX 格式）
   - **几何/物理意义**（如适用）
   - **使用条件**：什么情况下适用，什么情况下不适用
   - **典型例题**：至少 1 道例题，展示完整解题步骤
   - **易错点**：学生最容易出错的地方
3. **章节总结**：用要点形式归纳本章核心内容
4. **课后思考**：1-2 个值得深入思考的问题

### 格式要求：
- 使用 Markdown 层级标题（## 章、### 节、#### 知识点）
- 所有数学公式严格使用 LaTeX
- 关键术语首次出现时加粗
- 重要结论用 **加粗** 突出""")
        elif "知识结构图" in gt:
            sections.append("""
## 三、知识结构图

用层级列表和关系标注展示完整的知识体系：

- **第一层：学科分支** — 课程涵盖哪几个大的主题领域
- **第二层：章节脉络** — 每个主题下包含哪些章节，章节之间是什么关系（递进 → / 并列 ↔ / 依赖 →）
- **第三层：知识点网络** — 每章内的知识点及其关联：
  - 标注知识点的前置依赖（学习 B 之前需要先掌握 A）
  - 标注跨章节的知识关联
- **核心节点**用 **加粗** 突出
- 用 →（推导/递进）、←（反向引用）、↔（等价/关联）标注关系""")
        elif "自测题库" in gt:
            sections.append("""
## 四、自测题库

**重要：直接生成题目，不要先输出知识点回顾、章节复习、概念梳理等内容。开门见山，从第一道题开始。每道题在解析中简要说明所考查的知识点即可。**

生成高质量的练习题，覆盖全部重点和难点，题目数量以覆盖所有重要知识点为准：

### 单选题
- 覆盖所有重要知识点，数量不限
- 每道 4 个选项，标注正确答案
- 每个错误选项应该代表一种典型误解（并说明为什么错）
- 每题附详细解析

### 填空题
- 覆盖关键公式、定义中的关键词汇，数量不限
- 附完整答案解析

### 简答题
- 覆盖概念理解、定理陈述、方法比较，数量不限
- 附参考答案要点（列出得分点）

### 计算/证明题
- 覆盖重点计算方法，数量不限
- 附完整解题步骤和评分标准""")

    return sections


# 中文数字 → 资料类型映射（用于拆分 LLM 输出）
_CN_SECTION_MAP = {"一": "复习提纲", "二": "详细笔记", "三": "知识结构图", "四": "自测题库"}
_CN_NUMS = "一二三四五六七八九十"


def _split_by_sections(full_output: str, generate_types: list[str]) -> list[tuple[str, str]]:
    """按 ## N、section 标题拆分 LLM 输出，返回 [(type_name, content), ...]。

    只保留 generate_types 中已勾选的类型，按原始顺序返回。
    """
    import re

    pattern = r"\n(?=## [" + _CN_NUMS + r"]、)"
    raw_parts = re.split(pattern, full_output)

    result: list[tuple[str, str]] = []
    seen_types: set[str] = set()
    for part in raw_parts:
        part = part.strip()
        if not part:
            continue
        m = re.match(r"## ([" + _CN_NUMS + r"])、", part)
        if not m:
            if result:
                name, content = result[0]
                result[0] = (name, content + "\n\n" + part)
            continue
        cn = m.group(1)
        type_name = _CN_SECTION_MAP.get(cn)
        # 去重：同名章节只保留第一次出现
        if (
            type_name
            and type_name not in seen_types
            and any(type_name in gt for gt in generate_types)
        ):
            seen_types.add(type_name)
            result.append((type_name, part))

    return result


def _build_generation_prompt(
    merged_content: str, generate_types: list[str], custom_extra: str
) -> str:
    """根据合并内容和类型选择构建生成提示词（始终中文，发送给 LLM）。"""
    type_sections = _build_type_sections(generate_types)
    sections_text = "\n".join(type_sections)

    is_quiz_only = len(generate_types) == 1 and "自测题库" in generate_types[0]

    if is_quiz_only:
        task_desc = (
            "请根据以下课堂内容，生成一套高质量的自测题库。"
            "**注意：直接出题，不要先输出知识点回顾、复习提纲、概念梳理等前置内容。**"
        )
        global_reqs = """## 全局要求
- 使用 Markdown 排版，标题层级清晰（##、###、####）
- 所有数学公式使用 LaTeX（行内 $...$，独立公式 $$...$$）
- 开门见山，直接从题目开始，不要输出复习性内容
- 每道题附详细解析，解析中可简要提及所考查的知识点
- 题目难度应有梯度，覆盖基础概念到综合应用"""
    else:
        task_desc = "你是一位复习资料整理专家。请根据以下课堂内容，生成完整的复习材料。"
        global_reqs = """## 全局要求
- 使用 Markdown 排版，标题层级清晰（##、###、####）
- 所有数学公式使用 LaTeX（行内 $...$，独立公式 $$...$$）
- 关键术语首次出现时加粗
- 内容务必详尽完整，不要为了简短而省略任何知识点
- 不要使用「详见教材」「此处省略」等跳过性表述
- 即使课程材料对某些内容提及较少，也请基于你的专业知识补充完善，并标注「补充」
- 不要以教师口吻进行自我介绍（如"同学们好，我是XX老师"），直接输出复习材料内容
- 每个章节结束后直接进入下一章节，"
        "不要在章节末尾添加祝福语、鼓励语或总结语"
        "（如"祝考试顺利""希望这份资料有帮助"等）"""

    return f"""{task_desc}

## 课程内容

{merged_content}

## 输出要求

请按以下结构输出（Markdown 格式，适合打印和屏幕阅读）：
{sections_text}

{f"## 五、附加要求\n{custom_extra}" if custom_extra else ""}

{global_reqs}
"""


def _run_generation(
    cm,
    current,
    config,
    available_transcripts,
    use_transcripts,
    available_docs,
    use_docs,
    generate_types,
    custom_extra,
) -> None:
    """执行复习资料生成（在左栏内流式渲染）。"""
    selected_transcript_texts = [available_transcripts[i]["text"] for i in use_transcripts]
    selected_doc_texts = [available_docs[i]["text"] for i in use_docs]

    if not selected_transcript_texts and not selected_doc_texts:
        st.error(t("page2.no_sources"))
        return

    from src.llm.factory import get_llm
    from src.merger.content_merger import ContentMerger

    merger = ContentMerger()
    merged = merger.merge(
        transcript="\n\n".join(selected_transcript_texts) if selected_transcript_texts else None,
        parsed_docs=selected_doc_texts if selected_doc_texts else None,
    )

    merged_dir = cm.sub_dir(current, "merged")
    merged_file = merged_dir / "merged_content.md"
    merger.to_markdown(merged, merged_file)

    llm = get_llm(config.llm)

    prompt = _build_generation_prompt(merged.content, generate_types, custom_extra)

    checkpoint_path = merged_dir / "review_checkpoint.json"
    output_placeholder = st.empty()
    progress_text = st.empty()
    full_output = ""
    max_passes = 3
    pass_num = 0  # 在 except 块中需要访问

    # 检测未完成的生成
    if checkpoint_path.exists():
        try:
            ckpt = _json_module.loads(checkpoint_path.read_text("utf-8"))
            ckpt_timestamp = ckpt.get("timestamp", t("common.unknown"))
            ckpt_material = ckpt.get("generate_types", [t("common.unknown")])[0][:20]
            st.warning(
                t(
                    "page2.checkpoint_warning",
                    timestamp=ckpt_timestamp,
                    material=ckpt_material,
                    pass_num=ckpt.get("pass_num", 0),
                )
            )
            col_resume, col_discard = st.columns(2)
            if col_resume.button(t("page2.resume"), type="primary", use_container_width=True):
                full_output = ckpt.get("full_output", "")
                saved_generate_types = ckpt.get("generate_types", generate_types)
                saved_custom_extra = ckpt.get("custom_extra", custom_extra)
                generate_types = saved_generate_types
                custom_extra = saved_custom_extra
                prompt = _build_generation_prompt(merged.content, generate_types, custom_extra)
                resume_from = ckpt.get("pass_num", 1) + 1
            elif col_discard.button(t("page2.discard"), use_container_width=True):
                checkpoint_path.unlink(missing_ok=True)
                st.rerun()
            else:
                st.stop()  # 等待用户决策
            if full_output:
                pass_num = resume_from - 1  # 循环开始前会 +1
        except Exception:
            checkpoint_path.unlink(missing_ok=True)

    try:
        for pass_num in range(pass_num + 1, max_passes + 1):
            if pass_num == 1:
                progress_text.info(t("page2.generating"))
                current_messages = [{"role": "user", "content": prompt}]
            else:
                progress_text.info(t("page2.continuing", pass_num=pass_num))
                current_messages = [
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": full_output},
                    {
                        "role": "user",
                        "content": (
                            "你的输出因长度限制被截断，请从最后一个被截断的字/词/公式处继续。\n\n"
                            "规则：\n"
                            "1. 不要重复已经写过的任何内容，直接从断点接着写\n"
                            "2. 保持和上文完全一致的 Markdown 层级结构\n"
                            "3. 不要添加任何问候语、祝福语、总结语或开场白\n"
                            "4. 如果上一个字或公式被截断，先补全它\n"
                            "5. 所有要求的部分都生成完毕后，回复「[生成完毕]」"
                        ),
                    },
                ]

            pass_content = ""
            stream = llm.stream_chat(current_messages, temperature=0.3, max_tokens=None)
            for i, chunk in enumerate(stream):
                pass_content += chunk
                if i % 8 == 0:
                    output_placeholder.markdown(_normalize_latex(full_output + pass_content) + "▌")
            output_placeholder.markdown(_normalize_latex(full_output + pass_content) + "▌")

            full_output += pass_content

            # 每轮完成后保存检查点
            _ckpt = {
                "full_output": full_output,
                "pass_num": pass_num,
                "generate_types": generate_types,
                "custom_extra": custom_extra,
                "timestamp": _datetime.now().isoformat(),
            }
            checkpoint_path.write_text(
                _json_module.dumps(_ckpt, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            if len(pass_content) < 1500:
                break
            if "[生成完毕]" in pass_content:
                full_output = full_output.replace("[生成完毕]", "")
                break

        output_placeholder.markdown(_normalize_latex(full_output))
        progress_text.empty()

        # 清理 LLM 可能在末尾残留的祝福语/问候语
        import re as _re

        _closing_patterns = [
            r"\n*祝[^\n]{0,30}考试[^\n]{0,20}(?:顺利|成功)[^\n]*[！!。.]?",
            r"\n*希望[^\n]{0,30}(?:帮助|有用|顺利)[^\n]*[！!。.]?",
            r"\n*好的，?我们继续[^\n]*\n*",
        ]
        for _pat in _closing_patterns:
            full_output = _re.sub(_pat, "", full_output)

        checkpoint_path.unlink(missing_ok=True)

        # 按章节标题拆分为独立资料，每个类型单独保存
        import time as _time

        sections = _split_by_sections(full_output, generate_types)
        saved_count = 0
        for type_name, content in sections:
            cm.save_review_material(current, type_name, content)
            saved_count += 1
            if len(sections) > 1:
                _time.sleep(0.05)  # 确保时间戳不同，避免文件名冲突

        if saved_count == 0:
            # 回退：无法拆分时整篇保存
            primary_type = generate_types[0]
            for kw in ["复习提纲", "详细笔记", "知识结构图", "自测题库"]:
                if kw in primary_type:
                    primary_type = kw
                    break
            cm.save_review_material(current, primary_type, full_output)

        set_state("review_material", full_output)
        set_state("review_materials", [m.__dict__ for m in cm.list_review_materials(current)])

        st.success(t("page2.saved", chars=f"{len(full_output):,}"))
        st.rerun()

    except Exception as e:
        # 保存部分输出作为检查点，方便恢复
        if full_output:
            try:
                _ckpt = {
                    "full_output": full_output,
                    "pass_num": pass_num if pass_num > 0 else 1,
                    "generate_types": generate_types,
                    "custom_extra": custom_extra,
                    "timestamp": _datetime.now().isoformat(),
                }
                checkpoint_path.write_text(
                    _json_module.dumps(_ckpt, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            except Exception:
                pass
        st.error(t("page2.generate_fail", error=str(e)))


def _import_to_kb(cm, current, config, content: str) -> None:
    """将指定内容导入知识库。"""
    from src.knowledge.chroma_store import ChromaVectorStore
    from src.knowledge.chunker import MarkdownChunker
    from src.knowledge.embedder import get_embedder

    embedder = get_embedder(config.embedding)
    chunker = MarkdownChunker(config.chromadb.chunk_size, config.chromadb.chunk_overlap)

    chunks = chunker.chunk_text(content, {"source_type": "review", "course": current})
    texts = [c.text for c in chunks]
    metadatas = [c.metadata for c in chunks]

    chroma_config = config.chromadb
    chroma_config.persist_directory = str(cm.chroma_dir(current))
    chroma_config.collection_name = cm.sanitize_collection_name(current)

    store = ChromaVectorStore(chroma_config, embedder)
    # 清理旧的复习资料，避免重复导入累积
    try:
        store._collection.delete(where={"source_type": "review"})
    except Exception:
        pass
    store.add_documents(texts, metadatas)

    set_state("vector_store", store)
    set_state("chunker", chunker)
    set_state("embedder", embedder)
    set_state("vector_store_ready", True)

    state_obj = cm.load_state(current)
    state_obj.vector_store_ready = True
    cm.save_state(current, state_obj)


def _build_kb_from_sources(
    cm,
    current,
    config,
    available_docs,
    available_transcripts,
) -> None:
    """从所有源材料构建知识库。"""
    from src.knowledge.chroma_store import ChromaVectorStore
    from src.knowledge.chunker import MarkdownChunker
    from src.knowledge.embedder import get_embedder

    embedder = get_embedder(config.embedding)
    chunker = MarkdownChunker(config.chromadb.chunk_size, config.chromadb.chunk_overlap)

    chroma_config = config.chromadb
    chroma_config.persist_directory = str(cm.chroma_dir(current))
    chroma_config.collection_name = cm.sanitize_collection_name(current)
    store = ChromaVectorStore(chroma_config, embedder)

    all_chunks = []

    for d in available_docs:
        chunks = chunker.chunk_text(
            d["text"],
            {"source_type": "courseware", "source_file": d["name"], "course": current},
        )
        all_chunks.extend(chunks)

    for tr in available_transcripts:
        chunks = chunker.chunk_text(
            tr["text"],
            {"source_type": "transcript", "source_file": tr["name"], "course": current},
        )
        all_chunks.extend(chunks)

    if all_chunks:
        texts = [c.text for c in all_chunks]
        metadatas = [c.metadata for c in all_chunks]
        store.add_documents(texts, metadatas)

        set_state("vector_store", store)
        set_state("chunker", chunker)
        set_state("embedder", embedder)
        set_state("vector_store_ready", True)

        state_obj = cm.load_state(current)
        state_obj.vector_store_ready = True
        cm.save_state(current, state_obj)


init_session_state()
render_sidebar()
inject_workspace_layout()
inject_mermaid()

st.subheader(t("nav.workspace"))
st.caption(t("page2.caption"))

# ---- 课程检查 ----
current = get_state("current_course", "")
if not current:
    st.warning(t("common.no_course"))
    st.stop()

cm = get_state("course_manager")
config = get_state("app_config")

# ====================================================================
# 扫描可用的源材料
# ====================================================================
transcripts_dir = cm.sub_dir(current, "transcripts")
available_transcripts: list[dict] = []

asr_results = get_state("asr_results", [])
seen_names: set[str] = set()

for r in asr_results:
    if r.get("result") and r["name"] not in seen_names:
        available_transcripts.append({"name": r["name"], "text": r["result"].full_text})
        seen_names.add(r["name"])

for txt_file in sorted(transcripts_dir.glob("*_transcript.txt")):
    name = txt_file.stem.replace("_transcript", "")
    if name not in seen_names:
        try:
            text = txt_file.read_text(encoding="utf-8")
            if text.strip():
                available_transcripts.append({"name": name, "text": text})
                seen_names.add(name)
        except Exception:
            pass

# 扫描 AI 修正后的转录文本
for corrected_file in sorted(transcripts_dir.glob("*_corrected*.txt")):
    name = corrected_file.stem
    if name not in seen_names:
        try:
            text = corrected_file.read_text(encoding="utf-8")
            if text.strip():
                available_transcripts.append({"name": f"[AI修正] {name}", "text": text})
                seen_names.add(name)
        except Exception:
            pass

parsed_dir = cm.sub_dir(current, "parsed_docs")
available_docs: list[dict] = []

parsed_results = get_state("parsed_results", [])
seen_doc_names: set[str] = set()

for r in parsed_results:
    if r and r.markdown_content:
        doc_name = r.metadata.get("source_file", t("common.unknown"))
        if doc_name not in seen_doc_names:
            available_docs.append({"name": doc_name, "text": r.markdown_content})
            seen_doc_names.add(doc_name)

for md_file in sorted(parsed_dir.rglob("*.md")):
    if md_file.is_file():
        doc_name = md_file.parent.name if md_file.parent != parsed_dir else md_file.stem
        if doc_name not in seen_doc_names:
            try:
                text = md_file.read_text(encoding="utf-8")
                if text.strip():
                    available_docs.append({"name": doc_name, "text": text})
                    seen_doc_names.add(doc_name)
            except Exception:
                pass

# ====================================================================
# 知识库懒加载
# ====================================================================
vs_ready = get_state("vector_store_ready")
vector_store = get_state("vector_store")

if vs_ready and vector_store is None:
    try:
        from src.knowledge.chroma_store import ChromaVectorStore
        from src.knowledge.embedder import get_embedder

        embedder = get_state("embedder")
        if embedder is None:
            embedder = get_embedder(config.embedding)
            set_state("embedder", embedder)

        chroma_config = config.chromadb
        chroma_config.persist_directory = str(cm.chroma_dir(current))
        chroma_config.collection_name = cm.sanitize_collection_name(current)
        vector_store = ChromaVectorStore(chroma_config, embedder)
        set_state("vector_store", vector_store)
    except Exception as e:
        st.warning(t("page2.kb_load_fail", error=str(e)))
        set_state("vector_store_ready", False)
        vs_ready = False

# ====================================================================
# 左右分栏（独立滚动）
# ====================================================================
left_col, right_col = st.columns([0.55, 0.45])

# ============================
# 左栏: 复习资料（可独立滚动）
# ============================
with left_col:
    with st.container(key="workspace-left"):
        st.subheader(t("page2.review_materials"))

        # ---- 生成新资料（可折叠） ----
        with st.expander(
            f"+ {t('page2.new_generation')}",
            expanded=not bool(cm.list_review_materials(current)),
        ):
            st.caption(t("page2.select_sources"))

            if not available_transcripts and not available_docs:
                st.warning(t("page2.no_sources"))
            else:
                gen_col1, gen_col2 = st.columns(2)

                with gen_col1:
                    st.caption(f"**{t('page2.audio_transcripts')}**")
                    use_transcripts: list[int] = []
                    if available_transcripts:
                        for i, tr in enumerate(available_transcripts):
                            if st.checkbox(
                                t("page2.char_count_label", name=tr["name"], count=len(tr["text"])),
                                value=True,
                                key=f"gen_tx_{i}",
                            ):
                                use_transcripts.append(i)
                    else:
                        st.caption(t("page2.none_label"))

                with gen_col2:
                    st.caption(f"**{t('page2.slides_parsed')}**")
                    use_docs: list[int] = []
                    if available_docs:
                        for i, d in enumerate(available_docs):
                            if st.checkbox(
                                t("page2.char_count_label", name=d["name"], count=len(d["text"])),
                                value=True,
                                key=f"gen_doc_{i}",
                            ):
                                use_docs.append(i)
                    else:
                        st.caption(t("page2.none_label"))

                # 生成类型选项保持中文（用于 prompt 匹配逻辑）
                generate_types = st.multiselect(
                    t("page2.generate_type"),
                    options=[
                        "复习提纲（核心概念 + 重点/难点标注 + 公式定理）",
                        "详细笔记（逐章知识点详细梳理）",
                        "知识结构图（章节层级结构 + 知识关联）",
                        "自测题库（单选题 + 简答题 + 答案）",
                    ],
                    default=["复习提纲（核心概念 + 重点/难点标注 + 公式定理）"],
                    placeholder=t("page2.select_type_placeholder"),
                )

                custom_extra = ""
                if st.checkbox(t("page2.custom_extra")):
                    custom_extra = st.text_area(
                        t("page2.extra_requirement"),
                        placeholder=t("page2.extra_placeholder"),
                        height=60,
                    )

                if generate_types and (use_transcripts or use_docs):
                    if st.button(
                        t("page2.start_generate"), type="primary", use_container_width=True
                    ):
                        _run_generation(
                            cm,
                            current,
                            config,
                            available_transcripts,
                            use_transcripts,
                            available_docs,
                            use_docs,
                            generate_types,
                            custom_extra,
                        )

        # ---- 已保存资料 ----
        st.divider()
        st.caption(t("sidebar.saved_materials"))

        materials = cm.list_review_materials(current)
        set_state("review_materials", [m.__dict__ for m in materials])

        selected_mat = get_state("selected_material")

        if materials:
            # Tab 标签页切换（每个资料一个 Tab）
            tab_labels = []
            for m in materials:
                type_tag = _material_type_short(m.material_type)
                label = f"{type_tag} {m.display_name[:20]}"
                tab_labels.append(label)

            # 找到已选中或默认第一个
            tab_idx = 0
            if selected_mat:
                for i, m in enumerate(materials):
                    if m.filename == selected_mat:
                        tab_idx = i
                        break

            tabs = st.tabs(tab_labels)
            for i, (tab, m) in enumerate(zip(tabs, materials)):
                with tab:
                    # 标记选中
                    if selected_mat != m.filename:
                        set_state("selected_material", m.filename)

                    content = cm.load_review_material(current, m.filename)
                    if content:
                        st.caption(f"{m.display_name} · {m.created_at[:10]} · {m.char_count:,} 字")
                        st.divider()
                        with st.container():
                            _render_markdown(content)

                        col_dl, col_del, col_imp = st.columns([1, 1, 1])
                        col_dl.download_button(
                            t("page2.download_md"),
                            data=content.encode("utf-8"),
                            file_name=f"{m.display_name}.md",
                            mime="text/markdown",
                            use_container_width=True,
                            key=f"dl_{m.filename}",
                        )
                        if col_del.button(
                            t("page2.delete"), key=f"del_{m.filename}", use_container_width=True
                        ):
                            cm.delete_review_material(current, m.filename)
                            if selected_mat == m.filename:
                                set_state("selected_material", None)
                            set_state("review_materials", [])
                            st.rerun()

                        if col_imp.button(
                            t("page2.import_kb"),
                            key=f"import_{m.filename}",
                            use_container_width=True,
                        ):
                            with st.spinner(t("page2.building_index")):
                                try:
                                    _import_to_kb(cm, current, config, content)
                                    st.success(t("page2.imported_kb"))
                                    st.rerun()
                                except Exception as e:
                                    st.error(t("page2.import_fail", error=str(e)))
        else:
            st.caption(f"  {t('page2.no_materials_yet')}")

with right_col:
    with st.container(key="workspace-right"):
        # ============================
        # 右栏: 智能问答（聊天区可滚动，输入框始终可见）
        # ============================
        st.subheader(t("page2.qa_title"))

        # 知识库状态
        kb_col1, kb_col2, kb_col3 = st.columns([2, 1, 1])
        if vs_ready and vector_store:
            doc_count = vector_store.count()
            kb_col1.success(t("page2.kb_ready", count=doc_count))
        else:
            kb_col1.warning(t("page2.kb_not_ready"))

        if kb_col2.button(t("page2.build_kb"), use_container_width=True, disabled=vs_ready):
            with st.spinner(t("page2.building_kb")):
                try:
                    _build_kb_from_sources(
                        cm,
                        current,
                        config,
                        available_docs,
                        available_transcripts,
                    )
                    st.success(t("page2.kb_built"))
                    st.rerun()
                except Exception as e:
                    st.error(t("page2.build_fail", error=str(e)))

        if kb_col3.button(t("page2.clear"), use_container_width=True):
            if vector_store:
                vector_store.delete_collection()
            set_state("vector_store_ready", False)
            set_state("vector_store", None)
            set_state("chat_history", [])
            cm.save_chat_history(current, [])
            state_obj = cm.load_state(current)
            state_obj.vector_store_ready = False
            cm.save_state(current, state_obj)
            st.rerun()

        st.divider()

        # -- 聊天消息 --
        chat_history = get_state("chat_history", [])

        if chat_history:
            for i, msg in enumerate(chat_history):
                with st.chat_message(msg["role"]):
                    _render_markdown(msg["content"])

                    is_last_assistant = msg["role"] == "assistant" and i == len(chat_history) - 1

                    if msg.get("sources") and is_last_assistant:
                        col_src, col_btn = st.columns([20, 1])
                        with col_src:
                            with st.expander(t("page2.sources")):
                                for src in msg["sources"]:
                                    sim_score = f"{src.get('score', 0):.2f}"
                                    st.caption(
                                        f"**{src.get('source_file', t('common.unknown'))}** | "
                                        f"{t('page2.similarity', score=sim_score)}"
                                    )
                                    st.text(src.get("content", "")[:300])
                        with col_btn:
                            show_key = f"show_regen_{i}"
                            if st.button("↻", key=f"regen_toggle_{i}"):
                                set_state(show_key, not get_state(show_key, False))
                                st.rerun()

                        if get_state(show_key, False):
                            col_r1, col_r2, col_r3, col_r4 = st.columns([1, 1, 1, 8])
                            with col_r1:
                                if st.button(t("page2.regen"), key=f"regen_{i}"):
                                    set_state(show_key, False)
                                    chat_history.pop()
                                    set_state("chat_history", chat_history)
                                    set_state("regenerate_style", "default")
                                    st.rerun()
                            with col_r2:
                                if st.button(t("page2.regen_detail"), key=f"regen_d_{i}"):
                                    set_state(show_key, False)
                                    chat_history.pop()
                                    set_state("chat_history", chat_history)
                                    set_state("regenerate_style", "more_detail")
                                    st.rerun()
                            with col_r3:
                                if st.button(t("page2.regen_casual"), key=f"regen_c_{i}"):
                                    set_state(show_key, False)
                                    chat_history.pop()
                                    set_state("chat_history", chat_history)
                                    set_state("regenerate_style", "more_casual")
                                    st.rerun()

                    elif msg.get("sources"):
                        with st.expander(t("page2.sources")):
                            for src in msg["sources"]:
                                sim_score = f"{src.get('score', 0):.2f}"
                                st.caption(
                                    f"**{src.get('source_file', t('common.unknown'))}** | "
                                    f"{t('page2.similarity', score=sim_score)}"
                                )
                                st.text(src.get("content", "")[:300])

                    elif is_last_assistant:
                        col_empty, col_btn = st.columns([20, 1])
                        with col_btn:
                            show_key = f"show_regen_{i}"
                            if st.button("↻", key=f"regen_toggle_{i}"):
                                set_state(show_key, not get_state(show_key, False))
                                st.rerun()

                        if get_state(show_key, False):
                            col_r1, col_r2, col_r3, col_r4 = st.columns([1, 1, 1, 8])
                            with col_r1:
                                if st.button(t("page2.regen"), key=f"regen_{i}"):
                                    set_state(show_key, False)
                                    chat_history.pop()
                                    set_state("chat_history", chat_history)
                                    set_state("regenerate_style", "default")
                                    st.rerun()
                            with col_r2:
                                if st.button(t("page2.regen_detail"), key=f"regen_d_{i}"):
                                    set_state(show_key, False)
                                    chat_history.pop()
                                    set_state("chat_history", chat_history)
                                    set_state("regenerate_style", "more_detail")
                                    st.rerun()
                            with col_r3:
                                if st.button(t("page2.regen_casual"), key=f"regen_c_{i}"):
                                    set_state(show_key, False)
                                    chat_history.pop()
                                    set_state("chat_history", chat_history)
                                    set_state("regenerate_style", "more_casual")
                                    st.rerun()
        else:
            st.caption(t("page2.start_chat"))

        # -- 操作栏 --
        if chat_history:
            c1, c2 = st.columns(2)
            if c1.button(t("page2.clear_chat"), use_container_width=True):
                set_state("chat_history", [])
                cm.save_chat_history(current, [])
                st.rerun()
            with c2:
                export_text = "\n\n".join(f"**{m['role']}**: {m['content']}" for m in chat_history)
                st.download_button(
                    t("page2.export_chat"),
                    data=export_text.encode("utf-8"),
                    file_name=f"{current}_qa.md",
                    mime="text/markdown",
                    use_container_width=True,
                )

        # -- 输入区（固定底部） --
        regenerate_style = get_state("regenerate_style", "")

        with st.container(key="workspace-input"):
            st.divider()
            user_query = st.chat_input(
                t("page2.chat_placeholder") if vs_ready else t("page2.build_kb_first"),
                key="qa_chat_input",
                disabled=not vs_ready,
            )

            # 确定问题来源：新输入 or 重新生成
            query = ""
            style_instruction = ""

            if user_query and user_query.strip():
                query = user_query.strip()
                chat_history.append({"role": "user", "content": query})
            elif regenerate_style and chat_history and chat_history[-1]["role"] == "user":
                query = chat_history[-1]["content"]
                if regenerate_style == "more_detail":
                    style_instruction = (
                        "\n\n## 本次回答要求：请提供更加详细、深入的解答，"
                        "包含更多背景知识、推导过程和具体例子，力求内容全面深透。"
                    )
                elif regenerate_style == "more_casual":
                    style_instruction = (
                        "\n\n## 本次回答要求：请用更加口语化、通俗易懂的方式解答，"
                        "就像和朋友聊天一样，多用比喻和生活化的例子，让复杂概念变得容易理解。"
                    )
                set_state("regenerate_style", "")

            # 处理
            if query:
                set_state("qa_processing", True)

                try:
                    vector_store = get_state("vector_store")

                    # 分别检索原始材料（转录+课件）和复习资料，确保两种来源都有代表性
                    raw_filter = {"source_type": {"$in": ["transcript", "courseware"]}}
                    review_filter = {"source_type": "review"}

                    raw_results = vector_store.search(query, top_k=5, where=raw_filter)
                    review_results = vector_store.search(query, top_k=3, where=review_filter)

                    # 合并结果，原始材料优先
                    all_results = raw_results + review_results

                    context_parts = []
                    sources = []
                    source_label_map = {
                        "transcript": t("page2.source_transcript"),
                        "courseware": t("page2.source_courseware"),
                        "review": t("page2.source_review"),
                    }
                    for r in all_results:
                        source_type = r.metadata.get("source_type", t("common.unknown"))
                        source_label = source_label_map.get(source_type, source_type)

                        context_parts.append(
                            f"[来源类型: {source_label}"
                            f" | 文件: {r.metadata.get('source_file', t('common.unknown'))}]\n"
                            f"{r.content}"
                        )
                        sources.append(
                            {
                                "source_file": r.metadata.get("source_file", t("common.unknown")),
                                "source_type": source_type,
                                "score": round(r.score, 4),
                                "content": r.content,
                            }
                        )

                    context = "\n\n---\n\n".join(context_parts)

                    # 联网搜索补充
                    from src.search.web_search import search_web

                    web_results = search_web(query, max_results=3)
                    if web_results:
                        web_parts = []
                        for wr in web_results:
                            web_parts.append(
                                f"[网络搜索 | {wr['title']} | {wr['href']}]\n{wr['body']}"
                            )
                        web_context = "\n\n---\n\n".join(web_parts)
                        context = (
                            context
                            + "\n\n## 网络搜索结果（仅供参考，非课程材料）\n\n"
                            + web_context
                        )

                    from src.llm.factory import get_llm

                    llm = get_llm(config.llm)
                    system_prompt = llm.load_prompt("qa_system.txt", context=context)
                    if style_instruction:
                        system_prompt += style_instruction

                    messages = [{"role": "system", "content": system_prompt}]
                    for h in chat_history[-10:]:
                        if h["role"] != "system":
                            messages.append({"role": h["role"], "content": h["content"]})
                    messages.append({"role": "user", "content": query})

                    placeholder = st.empty()
                    full_response = ""

                    with st.spinner(t("page2.thinking")):
                        stream = llm.stream_chat(messages)
                        for chunk in stream:
                            full_response += chunk
                            placeholder.markdown(_normalize_latex(full_response) + "▌")
                    placeholder.markdown(_normalize_latex(full_response))

                    chat_history.append(
                        {
                            "role": "assistant",
                            "content": full_response,
                            "sources": sources,
                        }
                    )

                    cm.save_chat_history(current, chat_history)

                except Exception as e:
                    st.error(t("page2.qa_error", error=str(e)))
                    chat_history.append(
                        {
                            "role": "assistant",
                            "content": t("page2.qa_error_msg", error=str(e)),
                            "sources": [],
                        }
                    )
                finally:
                    set_state("qa_processing", False)
                    set_state("chat_history", chat_history)
                    st.rerun()

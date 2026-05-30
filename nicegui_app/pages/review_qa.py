"""复习与问答页面 — 左栏资料查看/生成 + 右栏智能问答。

NiceGUI PoC — 替代 pages/2_复习与问答.py。
"""

import asyncio
import json
from datetime import datetime

from nicegui import ui

from src.i18n import t

from ..components.sidebar import _ensure_services, _material_type_short, render_sidebar
from ..components.theme import inject_theme
from ..state import get_cache, get_user, set_cache, set_user

# ====================================================================
# LaTeX 预处理（简化版 — MathJax 3 自动渲染 $...$ / $$...$$）
# ====================================================================


def _normalize_latex(content: str) -> str:
    """统一 LaTeX 分隔符，修复中文紧贴 $ 的问题。"""
    import re

    content = re.sub(r"\\\(\s*", "$", content)
    content = re.sub(r"\s*\\\)", "$", content)
    content = re.sub(r"\\\[\s*", "$$", content)
    content = re.sub(r"\s*\\\]", "$$", content)
    content = re.sub(r"([一-鿿])\$", r"\1 $", content)
    content = re.sub(r"(\$)([一-鿿])", r"$ \2", content)
    return content


def _normalize_mermaid(content: str) -> str:
    """修复 Mermaid 11.x 不再支持的旧语法。"""
    import re

    # 1. graph → flowchart（Mermaid 11 移除了 graph 关键字）
    content = re.sub(
        r"```mermaid\s*\n\s*graph\s+(TD|TB|LR|BT|RL)\b",
        r"```mermaid\nflowchart \1",
        content,
        flags=re.IGNORECASE,
    )

    # 2. subgraph "title" → subgraph ["title"]（flowchart 要求节点式括号表示法）
    #    处理 subgraph + Unicode 花引号标题（LLM 经常生成 "" 而非 ""）
    content = re.sub(
        r"\n(\s*)subgraph\s+“([^”]+)”",
        r'\n\1subgraph ["\2"]',
        content,
    )
    #    处理 subgraph + ASCII 引号标题（旧 graph 风格）
    content = re.sub(
        r'\n(\s*)subgraph\s+"([^"]+)"',
        r'\n\1subgraph ["\2"]',
        content,
    )
    #    处理 subgraph + 无引号标题（如中文直接做标题）
    content = re.sub(
        r"\n(\s*)subgraph\s+(?![\[\"“”])([^\n{]+?)(\s+(?:TB|BT|LR|RL))?\s*\n",
        r'\n\1subgraph ["\2"]\3\n',
        content,
    )

    # 3. 将 subgraph 体内的 direction 移到声明行（Mermaid 11 不支持体内 direction）
    #    subgraph ["title"]\n    direction LR → subgraph LR ["title"]
    content = re.sub(
        r'(subgraph\s+)\[("[^"]*")\]\s*\n\s*direction\s+(TB|BT|LR|RL)\s*\n',
        r"\1\3 [\2]\n",
        content,
    )

    return content


def _normalize_content(content: str) -> str:
    """对 markdown 内容应用全部规范化处理。"""
    return _normalize_latex(_normalize_mermaid(content))


# ====================================================================
# Prompt 构建（从 Streamlit 版直接迁移，纯文本逻辑）
# ====================================================================


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


def _build_generation_prompt(
    merged_content: str, generate_types: list[str], custom_extra: str
) -> str:
    """根据合并内容和类型选择构建生成提示词。"""
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
        task_desc = (
            "你是一位经验丰富的大学教师，正在为学生准备复习资料。"
            "请根据以下课堂内容，生成完整的复习材料。"
        )
        global_reqs = """## 全局要求
- 使用 Markdown 排版，标题层级清晰（##、###、####）
- 所有数学公式使用 LaTeX（行内 $...$，独立公式 $$...$$）
- 关键术语首次出现时加粗
- 内容务必详尽完整，不要为了简短而省略任何知识点
- 不要使用「详见教材」「此处省略」等跳过性表述
- 即使课程材料对某些内容提及较少，也请基于你的专业知识补充完善，并标注「补充」"""

    return f"""{task_desc}

## 课程内容

{merged_content}

## 输出要求

请按以下结构输出（Markdown 格式，适合打印和屏幕阅读）：
{sections_text}

{f"## 五、附加要求\n{custom_extra}" if custom_extra else ""}

{global_reqs}
"""


# ====================================================================
# 异步 LLM 流式辅助
# ====================================================================


async def _stream_llm_to_element(llm, messages: list[dict], output_element, base_text: str = ""):
    """将 sync LLM stream_chat 转为 async，逐 chunk 更新 UI 元素。"""
    from concurrent.futures import ThreadPoolExecutor

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()
    stream = llm.stream_chat(messages, temperature=0.3, max_tokens=None)

    def _produce():
        try:
            for chunk in stream:
                loop.call_soon_threadsafe(queue.put_nowait, chunk)
        except Exception as exc:
            loop.call_soon_threadsafe(queue.put_nowait, exc)
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)

    ThreadPoolExecutor(max_workers=1).submit(_produce)

    result = base_text
    while True:
        chunk = await queue.get()
        if chunk is None:
            break
        if isinstance(chunk, Exception):
            raise chunk
        result += chunk
        output_element.set_content(_normalize_content(result) + "▌")

    output_element.set_content(_normalize_content(result))
    return result


# ====================================================================
# 生成与知识库操作
# ====================================================================


async def _run_generation(
    cm,
    course: str,
    config,
    available_transcripts: list[dict],
    use_transcripts: list[int],
    available_docs: list[dict],
    use_docs: list[int],
    generate_types: list[str],
    custom_extra: str,
    output_element,
    status_label,
) -> None:
    """异步执行复习资料生成（流式渲染到 output_element）。"""
    from src.llm.factory import get_llm
    from src.merger.content_merger import ContentMerger

    selected_transcript_texts = [available_transcripts[i]["text"] for i in use_transcripts]
    selected_doc_texts = [available_docs[i]["text"] for i in use_docs]

    if not selected_transcript_texts and not selected_doc_texts:
        ui.notify(t("page2.no_sources"), type="negative")
        return

    merger = ContentMerger()
    merged = merger.merge(
        transcript="\n\n".join(selected_transcript_texts) if selected_transcript_texts else None,
        parsed_docs=selected_doc_texts if selected_doc_texts else None,
    )

    merged_dir = cm.sub_dir(course, "merged")
    merged_file = merged_dir / "merged_content.md"
    merger.to_markdown(merged, merged_file)

    llm = get_llm(config.llm)
    prompt = _build_generation_prompt(merged.content, generate_types, custom_extra)

    checkpoint_path = merged_dir / "review_checkpoint.json"
    full_output = ""
    max_passes = 3
    pass_num = 0

    # 检查点处理：自动恢复（PoC 简化，后续可加确认对话框）
    if checkpoint_path.exists():
        try:
            ckpt = json.loads(checkpoint_path.read_text("utf-8"))
            full_output = ckpt.get("full_output", "")
            ckpt_pn = ckpt.get("pass_num", 0)
            if full_output:
                generate_types = ckpt.get("generate_types", generate_types)
                custom_extra = ckpt.get("custom_extra", custom_extra)
                prompt = _build_generation_prompt(merged.content, generate_types, custom_extra)
                pass_num = ckpt_pn
                ui.notify(
                    t(
                        "page2.checkpoint_warning",
                        timestamp=ckpt.get("timestamp", "unknown"),
                        material=generate_types[0][:20],
                        pass_num=ckpt_pn,
                    ),
                    type="info",
                )
        except Exception:
            checkpoint_path.unlink(missing_ok=True)

    try:
        for pass_num in range(pass_num + 1, max_passes + 1):
            if pass_num == 1:
                status_label.set_content(t("page2.generating"))
                current_messages = [{"role": "user", "content": prompt}]
            else:
                status_label.set_content(t("page2.continuing", pass_num=pass_num))
                current_messages = [
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": full_output},
                    {
                        "role": "user",
                        "content": (
                            "你上一次的输出被截断了，请从截断处继续生成剩余内容。"
                            "保持相同的 Markdown 结构和详细程度。"
                            "不要重复已经写过的内容，直接从断点接着写。"
                            "如果所有内容已经生成完毕，请回复「[生成完毕]」。"
                        ),
                    },
                ]

            pass_content = await _stream_llm_to_element(
                llm, current_messages, output_element, full_output
            )
            # Track just this pass's content for completion detection
            this_pass_content = pass_content[len(full_output) :]
            full_output = pass_content

            # 保存检查点
            ckpt = {
                "full_output": full_output,
                "pass_num": pass_num,
                "generate_types": generate_types,
                "custom_extra": custom_extra,
                "timestamp": datetime.now().isoformat(),
            }
            checkpoint_path.write_text(
                json.dumps(ckpt, ensure_ascii=False, indent=2), encoding="utf-8"
            )

            if len(this_pass_content) < 1500:
                break
            if "[生成完毕]" in this_pass_content:
                full_output = full_output.replace("[生成完毕]", "")
                output_element.set_content(_normalize_content(full_output))
                break

        status_label.set_content("")

        primary_type = generate_types[0]
        for kw in ["复习提纲", "详细笔记", "知识结构图", "自测题库"]:
            if kw in primary_type:
                primary_type = kw
                break

        checkpoint_path.unlink(missing_ok=True)
        cm.save_review_material(course, primary_type, full_output)
        set_cache("review_material", full_output)
        set_cache("review_materials", [m.__dict__ for m in cm.list_review_materials(course)])
        ui.notify(t("page2.saved", chars=f"{len(full_output):,}"), type="positive")
        # 刷新页面以显示新资料
        ui.navigate.reload()

    except Exception as e:
        if full_output:
            try:
                ckpt = {
                    "full_output": full_output,
                    "pass_num": pass_num if pass_num > 0 else 1,
                    "generate_types": generate_types,
                    "custom_extra": custom_extra,
                    "timestamp": datetime.now().isoformat(),
                }
                checkpoint_path.write_text(
                    json.dumps(ckpt, ensure_ascii=False, indent=2), encoding="utf-8"
                )
            except Exception:
                pass
        ui.notify(t("page2.generate_fail", error=str(e)), type="negative")


def _import_to_kb(cm, course: str, config, content: str) -> None:
    """将复习资料内容导入知识库。"""
    from src.knowledge.chroma_store import ChromaVectorStore
    from src.knowledge.chunker import MarkdownChunker
    from src.knowledge.embedder import get_embedder

    embedder = get_embedder(config.embedding)
    chunker = MarkdownChunker(config.chromadb.chunk_size, config.chromadb.chunk_overlap)

    chunks = chunker.chunk_text(content, {"source_type": "review", "course": course})
    texts = [c.text for c in chunks]
    metadatas = [c.metadata for c in chunks]

    chroma_config = config.chromadb
    chroma_config.persist_directory = str(cm.chroma_dir(course))
    chroma_config.collection_name = cm.sanitize_collection_name(course)

    store = ChromaVectorStore(chroma_config, embedder)
    try:
        store._collection.delete(where={"source_type": "review"})
    except Exception:
        pass
    store.add_documents(texts, metadatas)

    set_cache("vector_store", store)
    set_cache("chunker", chunker)
    set_cache("embedder", embedder)
    set_cache("vector_store_ready", True)

    state_obj = cm.load_state(course)
    state_obj.vector_store_ready = True
    cm.save_state(course, state_obj)


def _build_kb_from_sources(
    cm,
    course: str,
    config,
    available_docs: list[dict],
    available_transcripts: list[dict],
) -> None:
    """从所有源材料构建知识库。"""
    from src.knowledge.chroma_store import ChromaVectorStore
    from src.knowledge.chunker import MarkdownChunker
    from src.knowledge.embedder import get_embedder

    embedder = get_embedder(config.embedding)
    chunker = MarkdownChunker(config.chromadb.chunk_size, config.chromadb.chunk_overlap)

    chroma_config = config.chromadb
    chroma_config.persist_directory = str(cm.chroma_dir(course))
    chroma_config.collection_name = cm.sanitize_collection_name(course)
    store = ChromaVectorStore(chroma_config, embedder)

    all_chunks = []
    for d in available_docs:
        chunks = chunker.chunk_text(
            d["text"],
            {"source_type": "courseware", "source_file": d["name"], "course": course},
        )
        all_chunks.extend(chunks)

    for tr in available_transcripts:
        chunks = chunker.chunk_text(
            tr["text"],
            {"source_type": "transcript", "source_file": tr["name"], "course": course},
        )
        all_chunks.extend(chunks)

    if all_chunks:
        texts = [c.text for c in all_chunks]
        metadatas = [c.metadata for c in all_chunks]
        store.add_documents(texts, metadatas)

        set_cache("vector_store", store)
        set_cache("chunker", chunker)
        set_cache("embedder", embedder)
        set_cache("vector_store_ready", True)

        state_obj = cm.load_state(course)
        state_obj.vector_store_ready = True
        cm.save_state(course, state_obj)


# ====================================================================
# 页面构建
# ====================================================================


@ui.page("/review/{course_name}")
async def review_qa_page(course_name: str):
    """复习与问答页面。"""
    await ui.context.client.connected()
    inject_theme()
    render_sidebar()

    _ensure_services()
    cm = get_cache("course_manager")
    config = get_cache("app_config")

    # 确保用户状态同步
    set_user("current_course", course_name)

    # 直接 URL 导航时显式加载聊天历史和向量库状态
    # （侧边栏的 _load_course_data 仅在点击课程时触发）
    state_obj = cm.load_state(course_name)
    set_cache("vector_store_ready", state_obj.vector_store_ready)
    chat_hist = cm.load_chat_history(course_name)
    set_cache("chat_history", chat_hist)

    # ---- 扫描可用的源材料 ----
    transcripts_dir = cm.sub_dir(course_name, "transcripts")
    available_transcripts: list[dict] = []

    asr_results = get_cache("asr_results", [])
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

    parsed_dir = cm.sub_dir(course_name, "parsed_docs")
    available_docs: list[dict] = []
    seen_doc_names: set[str] = set()

    parsed_results = get_cache("parsed_results", [])
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

    # ---- 知识库懒加载 ----
    vs_ready = get_cache("vector_store_ready", False)
    # 直接 URL 导航时清理其他课程遗留的陈旧 vector_store
    last_course = get_cache("_last_review_course", "")
    if last_course != course_name:
        set_cache("vector_store", None)
        set_cache("_last_review_course", course_name)
    vector_store = get_cache("vector_store")

    if vs_ready and vector_store is None:
        try:
            from src.knowledge.chroma_store import ChromaVectorStore
            from src.knowledge.embedder import get_embedder

            embedder = get_cache("embedder")
            if embedder is None:
                embedder = get_embedder(config.embedding)
                set_cache("embedder", embedder)

            chroma_config = config.chromadb
            chroma_config.persist_directory = str(cm.chroma_dir(course_name))
            chroma_config.collection_name = cm.sanitize_collection_name(course_name)
            vector_store = ChromaVectorStore(chroma_config, embedder)
            set_cache("vector_store", vector_store)
        except Exception as e:
            ui.notify(t("page2.kb_load_fail", error=str(e)), type="warning")
            set_cache("vector_store_ready", False)
            vs_ready = False

    materials = cm.list_review_materials(course_name)
    set_cache("review_materials", [m.__dict__ for m in materials])

    # ================================================================
    # 主布局：左 55% + 右 45%，独立滚动
    # ================================================================
    with ui.row().classes("w-full").style("height: calc(100vh - 50px); overflow: hidden"):
        # ---- 左栏 ----
        with (
            ui.column()
            .classes("overflow-y-auto")
            .style("width: 55%; height: 100%; padding: 0 1rem")
        ):
            _build_left_panel(
                cm, course_name, config, available_transcripts, available_docs, materials
            )

        # ---- 右栏 ----
        with ui.column().style(
            "width: 45%; height: 100%; display: flex; flex-direction: column;"
            " padding: 0 1rem; border-left: 1px solid rgba(128,128,128,0.15);"
            " overflow: hidden"
        ):
            try:
                _build_right_panel(
                    cm,
                    course_name,
                    config,
                    vs_ready,
                    vector_store,
                    available_docs,
                    available_transcripts,
                )
            except Exception as e:
                import logging

                logging.getLogger(__name__).exception("_build_right_panel failed")
                ui.label(f"右侧面板加载失败: {e}").classes("text-negative q-pa-md")


def _build_left_panel(
    cm,
    course: str,
    config,
    available_transcripts: list[dict],
    available_docs: list[dict],
    materials: list,
) -> None:
    """构建左栏：复习资料查看 + 新资料生成。"""
    ui.label(t("page2.review_materials")).classes("text-h5 q-mb-md")

    # ---- 生成新资料 ----
    with ui.expansion(
        f"+ {t('page2.new_generation')}",
        value=not bool(materials),
    ).classes("w-full"):
        ui.label(t("page2.select_sources")).classes("text-caption")

        if not available_transcripts and not available_docs:
            ui.label(t("page2.no_sources")).classes("text-warning")
        else:
            with ui.row().classes("w-full"):
                with ui.column().classes("flex-1"):
                    ui.label(t("page2.audio_transcripts")).classes("font-bold text-caption")
                    use_transcripts: list[int] = []
                    if available_transcripts:
                        for i, tr in enumerate(available_transcripts):
                            cb = ui.checkbox(
                                t("page2.char_count_label", name=tr["name"], count=len(tr["text"])),
                                value=True,
                            )
                            use_transcripts.append(i)  # default all selected
                            cb.on_value_change(
                                lambda e, idx=i: _toggle_list(use_transcripts, idx, e.value)
                            )
                    else:
                        ui.label(t("page2.none_label")).classes("text-caption")

                with ui.column().classes("flex-1"):
                    ui.label(t("page2.slides_parsed")).classes("font-bold text-caption")
                    use_docs: list[int] = []
                    if available_docs:
                        for i, d in enumerate(available_docs):
                            cb = ui.checkbox(
                                t("page2.char_count_label", name=d["name"], count=len(d["text"])),
                                value=True,
                            )
                            use_docs.append(i)  # default all selected
                            cb.on_value_change(
                                lambda e, idx=i: _toggle_list(use_docs, idx, e.value)
                            )
                    else:
                        ui.label(t("page2.none_label")).classes("text-caption")

            generate_types_select = ui.select(
                options=[
                    "复习提纲（核心概念 + 重点/难点标注 + 公式定理）",
                    "详细笔记（逐章知识点详细梳理）",
                    "知识结构图（章节层级结构 + 知识关联）",
                    "自测题库（单选题 + 简答题 + 答案）",
                ],
                value=["复习提纲（核心概念 + 重点/难点标注 + 公式定理）"],
                multiple=True,
                label=t("page2.generate_type"),
            ).classes("w-full")

            custom_extra = ui.textarea(
                t("page2.extra_requirement"),
                placeholder=t("page2.extra_placeholder"),
            ).classes("w-full")
            custom_extra.visible = False

            def toggle_custom():
                custom_extra.visible = not custom_extra.visible

            ui.checkbox(t("page2.custom_extra"), on_change=lambda e: toggle_custom())

            status_label = ui.label("").classes("text-info")

            # 生成输出区
            output_md = ui.markdown("", extras=["mermaid", "fenced-code-blocks", "tables"]).classes(
                "min-h-[100px] border rounded q-pa-sm"
            )

            async def on_generate():
                status_label.set_content(t("page2.generating"))
                output_md.set_content("▌")
                await _run_generation(
                    cm,
                    course,
                    config,
                    available_transcripts,
                    use_transcripts,
                    available_docs,
                    use_docs,
                    generate_types_select.value,
                    custom_extra.value,
                    output_md,
                    status_label,
                )

            ui.button(t("page2.start_generate"), on_click=on_generate, color="primary").classes(
                "w-full q-mt-md"
            )

    ui.separator()

    # ---- 已保存资料 ----
    ui.label(t("sidebar.saved_materials")).classes("text-caption")

    selected_mat = get_user("selected_material")

    if materials:
        with ui.tabs() as tabs:
            tab_list = []
            for m in materials:
                type_tag = _material_type_short(m.material_type)
                label = f"{type_tag} {m.display_name[:20]}"
                tab_list.append(ui.tab(label))

        with ui.tab_panels(tabs, value=tab_list[0] if tab_list else None).classes("w-full"):
            for i, (m, tab) in enumerate(zip(materials, tab_list)):
                with ui.tab_panel(tab):
                    if selected_mat != m.filename:
                        set_user("selected_material", m.filename)

                    content = cm.load_review_material(course, m.filename)
                    if content:
                        ui.label(
                            f"{m.display_name} · {m.created_at[:10]} · {m.char_count:,} 字"
                        ).classes("text-caption")
                        ui.separator()
                        ui.markdown(
                            _normalize_content(content),
                            extras=["mermaid", "fenced-code-blocks", "tables"],
                        )

                        with ui.row().classes("gap-2 q-mt-md"):

                            def _make_download(content_bytes, filename):
                                def handler():
                                    ui.download.content(
                                        content_bytes, filename=filename, media_type="text/markdown"
                                    )

                                return handler

                            ui.button(
                                t("page2.download_md"),
                                on_click=_make_download(
                                    content.encode("utf-8"), f"{m.display_name}.md"
                                ),
                            ).props("flat").classes("flex-1")

                            def _make_delete_handler(filename, mat_type):
                                def handler():
                                    cm.delete_review_material(course, filename)
                                    if get_user("selected_material") == filename:
                                        set_user("selected_material", None)
                                    set_cache("review_materials", [])
                                    ui.navigate.reload()

                                return handler

                            ui.button(
                                t("page2.delete"),
                                on_click=_make_delete_handler(m.filename, m.material_type),
                            ).props("flat").classes("flex-1")

                            def _make_import_handler(content_to_import):
                                def handler():
                                    try:
                                        _import_to_kb(cm, course, config, content_to_import)
                                        ui.notify(t("page2.imported_kb"), type="positive")
                                        ui.navigate.reload()
                                    except Exception as e:
                                        ui.notify(
                                            t("page2.import_fail", error=str(e)),
                                            type="negative",
                                        )

                                return handler

                            ui.button(
                                t("page2.import_kb"),
                                on_click=_make_import_handler(content),
                            ).props("flat").classes("flex-1")
    else:
        ui.label(f"  {t('page2.no_materials_yet')}").classes("text-caption text-grey")


def _build_right_panel(
    cm,
    course: str,
    config,
    vs_ready: bool,
    vector_store,
    available_docs: list[dict],
    available_transcripts: list[dict],
) -> None:
    """构建右栏：智能问答聊天。"""
    ui.label(t("page2.qa_title")).classes("text-h5 q-mb-md")

    # ---- 知识库状态 ----
    with ui.row().classes("w-full items-center gap-2"):
        if vs_ready and vector_store:
            try:
                doc_count = vector_store.count()
            except Exception:
                doc_count = 0
            ui.label(t("page2.kb_ready", count=doc_count)).classes("text-positive")
        else:
            ui.label(t("page2.kb_not_ready")).classes("text-warning")

        async def on_build_kb():
            try:
                _build_kb_from_sources(cm, course, config, available_docs, available_transcripts)
                ui.notify(t("page2.kb_built"), type="positive")
                ui.navigate.reload()
            except Exception as e:
                ui.notify(t("page2.build_fail", error=str(e)), type="negative")

        kb_btn = ui.button(
            t("page2.build_kb"),
            on_click=on_build_kb,
        ).props("flat dense")
        kb_btn.enabled = not vs_ready

        def on_clear_kb():
            vs = get_cache("vector_store")
            if vs:
                vs.delete_collection()
            set_cache("vector_store_ready", False)
            set_cache("vector_store", None)
            set_cache("chat_history", [])
            cm.save_chat_history(course, [])
            state_obj = cm.load_state(course)
            state_obj.vector_store_ready = False
            cm.save_state(course, state_obj)
            ui.navigate.reload()

        ui.button(t("page2.clear"), on_click=on_clear_kb).props("flat dense")

    ui.separator()

    # ---- 聊天消息 ----
    chat_history: list[dict] = get_cache("chat_history", [])

    # ---- 操作栏（固定在消息上方） ----
    if chat_history:
        with ui.row().classes("w-full gap-2").style("flex: 0 0 auto"):

            def on_clear_chat():
                set_cache("chat_history", [])
                cm.save_chat_history(course, [])
                ui.navigate.reload()

            ui.button(t("page2.clear_chat"), on_click=on_clear_chat).props("flat dense").classes(
                "flex-1"
            )

            export_text = "\n\n".join(f"**{m['role']}**: {m['content']}" for m in chat_history)

            def export_chat():
                ui.download.content(
                    export_text.encode("utf-8"),
                    filename=f"{course}_qa.md",
                    media_type="text/markdown",
                )

            ui.button(t("page2.export_chat"), on_click=export_chat).props("flat dense").classes(
                "flex-1"
            )

    # ---- 消息容器（唯一可滚动区域） ----
    messages_container = ui.column().style("flex: 1 1 auto; overflow-y: auto; min-height: 0")

    with messages_container:
        if chat_history:
            for msg in chat_history:
                _render_chat_message(msg)
        else:
            ui.label(t("page2.start_chat")).classes("text-caption text-grey q-mt-xl text-center")

    # ---- 输入区（固定底部，Flex 末位） ----
    with ui.card().classes("w-full").style("flex: 0 0 auto"):
        with ui.row().classes("w-full items-center gap-2"):
            query_input = (
                ui.input(
                    placeholder=t("page2.chat_placeholder")
                    if vs_ready
                    else t("page2.build_kb_first"),
                )
                .props("rounded outlined")
                .classes("flex-1")
            )
            query_input._enabled = vs_ready

            async def on_send():
                query = query_input.value
                if not query or not query.strip():
                    return
                query = query.strip()
                query_input.value = ""

                chat_history.append({"role": "user", "content": query})

                # Add to UI immediately
                with messages_container:
                    _render_chat_message({"role": "user", "content": query})

                try:
                    vs = get_cache("vector_store")
                    if vs is None:
                        ui.notify(t("page2.kb_not_ready"), type="warning")
                        return

                    raw_filter = {"source_type": {"$in": ["transcript", "courseware"]}}
                    review_filter = {"source_type": "review"}

                    raw_results = vs.search(query, top_k=5, where=raw_filter)
                    review_results = vs.search(query, top_k=3, where=review_filter)
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

                    from src.llm.factory import get_llm

                    llm = get_llm(config.llm)
                    system_prompt = llm.load_prompt("qa_system.txt", context=context)

                    llm_messages = [{"role": "system", "content": system_prompt}]
                    for h in chat_history[-10:]:
                        if h["role"] != "system":
                            llm_messages.append({"role": h["role"], "content": h["content"]})
                    llm_messages.append({"role": "user", "content": query})

                    # 流式响应
                    with messages_container:
                        response_md = ui.markdown(
                            "▌", extras=["mermaid", "fenced-code-blocks", "tables"]
                        )

                    full_response = await _stream_llm_to_element(llm, llm_messages, response_md)

                    chat_history.append(
                        {
                            "role": "assistant",
                            "content": full_response,
                            "sources": sources,
                        }
                    )
                    cm.save_chat_history(course, chat_history)
                    set_cache("chat_history", chat_history)

                except Exception as e:
                    ui.notify(t("page2.qa_error", error=str(e)), type="negative")
                    chat_history.append(
                        {
                            "role": "assistant",
                            "content": t("page2.qa_error_msg", error=str(e)),
                            "sources": [],
                        }
                    )

            query_input.on("keydown.enter", lambda: on_send())
            ui.button(t("page2.send"), on_click=on_send, color="primary").props("rounded")


def _render_chat_message(msg: dict) -> None:
    """渲染一条聊天消息气泡。"""
    with ui.chat_message(
        text=msg["content"],
        name=msg["role"].capitalize(),
        sent=msg["role"] == "user",
    ):
        if msg.get("sources"):
            with ui.expansion(t("page2.sources")):
                for src in msg["sources"]:
                    ui.label(
                        f"**{src.get('source_file', t('common.unknown'))}** | "
                        f"{t('page2.similarity', score=f'{src.get("score", 0):.2f}')}"
                    ).classes("text-caption")
                    ui.code(src.get("content", "")[:300]).classes("text-caption")


def _toggle_list(lst: list[int], idx: int, checked: bool) -> None:
    """辅助：根据 checkbox 状态添加/移除列表中的索引。"""
    if checked and idx not in lst:
        lst.append(idx)
    elif not checked and idx in lst:
        lst.remove(idx)

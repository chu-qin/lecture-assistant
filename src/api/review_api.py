"""复习与问答页面 API — FastAPI 路由。

复用现有 src/ 模块，不修改它们。提供课程列表、资料查看、
资料生成（SSE 流式）、RAG 问答（SSE 流式）四个接口。
"""

import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from src.config import get_config
from src.course_manager import CourseManager
from src.llm.factory import get_llm
from src.merger.content_merger import ContentMerger

logger = logging.getLogger(__name__)

app = FastAPI(title="Lecture Assistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- 初始化 ----
_config = get_config()
_cm = CourseManager(_config.project.data_dir)

# ---- 静态文件（HTML 前端） ----
_assets_dir = Path(__file__).resolve().parent.parent.parent / "assets"
_assets_dir.mkdir(exist_ok=True)
app.mount("/assets", StaticFiles(directory=str(_assets_dir)), name="assets")


# ================================================================
# Helper: LaTeX normalization (replicated from page2 to avoid importing Streamlit page)
# ================================================================

_HTML_RE = re.compile(r"<[^>]+>")


def _normalize_latex(content: str) -> str:
    """标准化 LaTeX 分隔符，转义未配对的 $。"""
    content = re.sub(r"\\\(\s*", "$", content)
    content = re.sub(r"\s*\\\)", "$", content)
    content = re.sub(r"\\\[\s*", "$$", content)
    content = re.sub(r"\s*\\\]", "$$", content)
    content = re.sub(r"([一-鿿　-〿＀-￯])\$", r"\1 $", content)
    content = re.sub(r"\$([一-鿿　-〿＀-￯])", r"$ \1", content)
    return _scan_math_delimiters(content)


def _scan_math_delimiters(text: str) -> str:
    result: list[str] = []
    i = 0
    n = len(text)

    while i < n:
        if i + 1 < n and text[i : i + 2] == "$$":
            closer = text.find("$$", i + 2)
            if closer != -1:
                inner = _HTML_RE.sub("", text[i + 2 : closer])
                result.append("$$" + inner + "$$")
                i = closer + 2
            else:
                result.append("\\$\\$")
                i += 2
            continue

        if text[i] == "$":
            j = i + 1
            found = False
            while j < n:
                if text[j] == "$":
                    if j + 1 < n and text[j : j + 2] == "$$":
                        closer2 = text.find("$$", j + 2)
                        if closer2 != -1:
                            j = closer2 + 2
                        else:
                            j += 2
                        continue
                    inner = _HTML_RE.sub("", text[i + 1 : j])
                    result.append("$" + inner + "$")
                    i = j + 1
                    found = True
                    break
                j += 1

            if not found:
                result.append("\\$")
                i += 1
            continue

        result.append(text[i])
        i += 1

    return "".join(result)


# ================================================================
# Helper: prompt building (replicated from page2)
# ================================================================

_CN_NUMS = "一二三四五六七八九十"
_CN_SECTION_MAP = {"一": "复习提纲", "二": "详细笔记", "三": "知识结构图", "四": "自测题库"}


def _build_type_sections(generate_types: list[str]) -> list[str]:
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
- 每个章节结束后直接进入下一章节，不要在章节末尾添加祝福语、鼓励语或总结语"""

    return f"""{task_desc}

## 课程内容

{merged_content}

## 输出要求

请按以下结构输出（Markdown 格式，适合打印和屏幕阅读）：
{sections_text}

{f"## 五、附加要求\n{custom_extra}" if custom_extra else ""}

{global_reqs}
"""


def _split_by_sections(full_output: str, generate_types: list[str]) -> list[tuple[str, str]]:
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
        if type_name and type_name not in seen_types and any(type_name in gt for gt in generate_types):
            seen_types.add(type_name)
            result.append((type_name, part))
    return result


# ================================================================
# Helper: source scanning (replicated from page2)
# ================================================================

def _scan_sources(course_name: str) -> tuple[list[dict], list[dict]]:
    """扫描课程下的转录文件和解析文档。返回 (transcripts, docs)。"""
    transcripts: list[dict] = []
    docs: list[dict] = []
    seen_tx: set[str] = set()
    seen_doc: set[str] = set()

    transcripts_dir = _cm.sub_dir(course_name, "transcripts")
    for txt_file in sorted(transcripts_dir.glob("*_transcript.txt")):
        name = txt_file.stem.replace("_transcript", "")
        if name not in seen_tx:
            try:
                text = txt_file.read_text(encoding="utf-8")
                if text.strip():
                    transcripts.append({"name": name, "text": text})
                    seen_tx.add(name)
            except Exception:
                pass

    for corrected_file in sorted(transcripts_dir.glob("*_corrected*.txt")):
        name = corrected_file.stem
        if name not in seen_tx:
            try:
                text = corrected_file.read_text(encoding="utf-8")
                if text.strip():
                    transcripts.append({"name": f"[AI修正] {name}", "text": text})
                    seen_tx.add(name)
            except Exception:
                pass

    parsed_dir = _cm.sub_dir(course_name, "parsed_docs")
    for md_file in sorted(parsed_dir.rglob("*.md")):
        if md_file.is_file():
            doc_name = md_file.parent.name if md_file.parent != parsed_dir else md_file.stem
            if doc_name not in seen_doc:
                try:
                    text = md_file.read_text(encoding="utf-8")
                    if text.strip():
                        docs.append({"name": doc_name, "text": text})
                        seen_doc.add(doc_name)
                except Exception:
                    pass

    return transcripts, docs


# ================================================================
# Routes
# ================================================================


@app.get("/api/courses")
async def list_courses():
    """返回课程列表，含每门课的统计信息。"""
    courses = _cm.list_courses()
    result = []
    for name in courses:
        stats = _cm.get_review_stats(name)
        materials = _cm.list_review_materials(name)
        result.append({
            "name": name,
            "audio_files": stats["audio_files"],
            "courseware_files": stats["courseware_files"],
            "transcripts": stats["transcripts"],
            "review_materials": stats["review_materials"],
            "kb_ready": stats["vector_store_ready"],
            "materials": [
                {
                    "filename": m.filename,
                    "material_type": m.material_type,
                    "display_name": m.display_name,
                    "created_at": m.created_at,
                    "char_count": m.char_count,
                }
                for m in materials
            ],
        })
    return {"courses": result}


@app.get("/api/courses/{course_id}/materials")
async def get_materials(course_id: str):
    """返回指定课程的所有已保存资料（含内容）。"""
    if course_id not in _cm.list_courses():
        raise HTTPException(status_code=404, detail=f"课程不存在: {course_id}")

    materials = _cm.list_review_materials(course_id)
    result = []
    for m in materials:
        content = _cm.load_review_material(course_id, m.filename)
        result.append({
            "filename": m.filename,
            "material_type": m.material_type,
            "display_name": m.display_name,
            "created_at": m.created_at,
            "char_count": m.char_count,
            "content": content or "",
        })
    return {"materials": result}


@app.get("/api/courses/{course_id}/sources")
async def get_sources(course_id: str):
    """返回课程的可用源材料（转录 + 课件），供生成资料时选择。"""
    if course_id not in _cm.list_courses():
        raise HTTPException(status_code=404, detail=f"课程不存在: {course_id}")

    transcripts, docs = _scan_sources(course_id)
    return {
        "transcripts": [{"name": t["name"], "char_count": len(t["text"])} for t in transcripts],
        "docs": [{"name": d["name"], "char_count": len(d["text"])} for d in docs],
    }


@app.post("/api/courses/{course_id}/generate")
async def generate_material(course_id: str, request: Request):
    """SSE 流式生成复习资料。"""
    if course_id not in _cm.list_courses():
        raise HTTPException(status_code=404, detail=f"课程不存在: {course_id}")

    body = await request.json()
    material_types: list[str] = body.get("material_types", ["复习提纲（核心概念 + 重点/难点标注 + 公式定理）"])
    custom_extra: str = body.get("custom_extra", "")

    # 扫描源材料
    transcripts, docs = _scan_sources(course_id)

    if not transcripts and not docs:
        raise HTTPException(status_code=400, detail="该课程没有任何源材料，请先上传课堂录音或课件。")

    async def event_stream():
        try:
            # 合并内容
            merger = ContentMerger()
            merged = merger.merge(
                transcript="\n\n".join(t["text"] for t in transcripts) if transcripts else None,
                parsed_docs=[d["text"] for d in docs] if docs else None,
            )

            merged_dir = _cm.sub_dir(course_id, "merged")
            merged_dir.mkdir(parents=True, exist_ok=True)
            merged_file = merged_dir / "merged_content.md"
            merger.to_markdown(merged, merged_file)

            # 构建 prompt
            llm = get_llm(_config.llm)
            prompt = _build_generation_prompt(merged.content, material_types, custom_extra)

            full_output = ""
            max_passes = 3

            for pass_num in range(1, max_passes + 1):
                if pass_num == 1:
                    yield f"data: {json.dumps({'type': 'status', 'message': '正在生成...'})}\n\n"
                    current_messages = [{"role": "user", "content": prompt}]
                else:
                    yield f"data: {json.dumps({'type': 'status', 'message': f'内容较长，正在续写（第{pass_num}轮）...'})}\n\n"
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
                for chunk in stream:
                    pass_content += chunk
                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"

                full_output += pass_content

                if len(pass_content) < 1500:
                    break
                if "[生成完毕]" in pass_content:
                    full_output = full_output.replace("[生成完毕]", "")
                    break

            # 清理尾部
            _closing_patterns = [
                r"\n*祝[^\n]{0,30}考试[^\n]{0,20}(?:顺利|成功)[^\n]*[！!。.]?",
                r"\n*希望[^\n]{0,30}(?:帮助|有用|顺利)[^\n]*[！!。.]?",
                r"\n*好的，?我们继续[^\n]*\n*",
            ]
            for pat in _closing_patterns:
                full_output = re.sub(pat, "", full_output)

            full_output = _normalize_latex(full_output)

            # 按章节拆分并保存
            sections = _split_by_sections(full_output, material_types)
            saved_materials = []
            for type_name, content in sections:
                file_path = _cm.save_review_material(course_id, type_name, content)
                saved_materials.append({"material_type": type_name, "display_name": type_name, "file": str(file_path)})
                if len(sections) > 1:
                    time.sleep(0.05)

            if not saved_materials:
                primary_type = material_types[0]
                for kw in ["复习提纲", "详细笔记", "知识结构图", "自测题库"]:
                    if kw in primary_type:
                        primary_type = kw
                        break
                file_path = _cm.save_review_material(course_id, primary_type, full_output)
                saved_materials.append({"material_type": primary_type, "display_name": primary_type, "file": str(file_path)})

            yield f"data: {json.dumps({'type': 'done', 'materials': saved_materials, 'total_chars': len(full_output)})}\n\n"

        except Exception as e:
            logger.exception("Generation failed for course %s", course_id)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/courses/{course_id}/chat")
async def chat(course_id: str, request: Request):
    """SSE 流式 RAG 问答。"""
    if course_id not in _cm.list_courses():
        raise HTTPException(status_code=404, detail=f"课程不存在: {course_id}")

    body = await request.json()
    message: str = body.get("message", "")
    history: list[dict] = body.get("history", [])

    if not message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")

    # 检查知识库状态
    state = _cm.load_state(course_id)
    if not state.vector_store_ready:
        raise HTTPException(status_code=400, detail="知识库未构建，请先生成或导入复习资料。")

    async def event_stream():
        try:
            from src.knowledge.chroma_store import ChromaVectorStore
            from src.knowledge.embedder import get_embedder

            embedder = get_embedder(_config.embedding)

            chroma_config = _config.chromadb
            chroma_config.persist_directory = str(_cm.chroma_dir(course_id))
            chroma_config.collection_name = _cm.sanitize_collection_name(course_id)
            store = ChromaVectorStore(chroma_config, embedder)

            # 检索
            raw_filter = {"source_type": {"$in": ["transcript", "courseware"]}}
            review_filter = {"source_type": "review"}

            raw_results = store.search(message, top_k=5, where=raw_filter)
            review_results = store.search(message, top_k=3, where=review_filter)
            all_results = raw_results + review_results

            source_label_map = {
                "transcript": "课堂录音",
                "courseware": "课件",
                "review": "复习资料",
            }
            context_parts = []
            sources = []
            for r in all_results:
                source_type = r.metadata.get("source_type", "未知")
                source_label = source_label_map.get(source_type, source_type)
                context_parts.append(
                    f"[来源类型: {source_label}"
                    f" | 文件: {r.metadata.get('source_file', '未知')}]\n{r.content}"
                )
                sources.append({
                    "source_file": r.metadata.get("source_file", "未知"),
                    "source_type": source_type,
                    "score": round(r.score, 4),
                    "content": r.content,
                })

            context = "\n\n---\n\n".join(context_parts)

            # 联网搜索
            try:
                from src.search.web_search import search_web

                web_results = search_web(message, max_results=3)
                if web_results:
                    web_parts = []
                    for wr in web_results:
                        web_parts.append(
                            f"[网络搜索 | {wr['title']} | {wr['href']}]\n{wr['body']}"
                        )
                    web_context = "\n\n---\n\n".join(web_parts)
                    context = context + "\n\n## 网络搜索结果（仅供参考，非课程材料）\n\n" + web_context
            except Exception:
                pass

            # 构建消息
            llm = get_llm(_config.llm)
            system_prompt = llm.load_prompt("qa_system.txt", context=context)

            messages = [{"role": "system", "content": system_prompt}]
            for h in history[-10:]:
                if h.get("role") != "system":
                    messages.append({"role": h["role"], "content": h["content"]})
            messages.append({"role": "user", "content": message})

            full_response = ""
            stream = llm.stream_chat(messages)
            for chunk in stream:
                full_response += chunk
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"

            yield f"data: {json.dumps({'type': 'done', 'content': _normalize_latex(full_response), 'sources': sources})}\n\n"

        except Exception as e:
            logger.exception("Chat failed for course %s", course_id)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
